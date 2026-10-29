package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import io.netty.buffer.Unpooled;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.util.EnumSet;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.levelgen.Heightmap;

/**
 * `chunk`: vanilla's chunk sections and heightmaps, with the vanilla data pack's block tags, run by
 * a list of operations, each result written to one blob (rig/PROTOCOL.md).
 *
 * <p>A {@code LevelChunk} needs a whole level, so the chunk is a {@code ProtoChunk}, whose sections,
 * heightmaps and {@code getBlockState} are the same, and {@code set} does what
 * {@code LevelChunk.setBlockState} does to them: it sets the state in its section, and updates the
 * four heightmaps a chunk in the world keeps, in its order.
 */
final class ChunkProbe implements Probe {
    private static final Heightmap.Types[] KINDS = Heightmap.Types.values();
    private static final Heightmap.Types[] KEPT = {
        Heightmap.Types.MOTION_BLOCKING, Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, Heightmap.Types.OCEAN_FLOOR, Heightmap.Types.WORLD_SURFACE,
    };
    private static final Field[] COUNTS = {
        field("nonEmptyBlockCount"), field("tickingBlockCount"), field("fluidCount"), field("tickingFluidCount"),
    };

    @Override
    public String name() {
        return "chunk";
    }

    @Override
    public int version() {
        return 1;
    }

    private static Field field(String name) {
        try {
            Field f = LevelChunkSection.class.getDeclaredField(name);
            f.setAccessible(true);
            return f;
        } catch (NoSuchFieldException e) {
            throw new IllegalStateException("LevelChunkSection has no " + name, e);
        }
    }

    /** The probe's 64-bit LCG, as `palette`'s. */
    private static final class Draws {
        private long x;

        Draws(long seed) {
            x = seed;
        }

        int next() {
            x = x * 6364136223846793005L + 1442695040888963407L;
            return (int) (x >>> 33);
        }
    }

    /** One operation: its name and its arguments. */
    private record Op(JsonArray items, int index) {
        String name() {
            return Args.asString(items.get(0), "operation " + index + "'s name");
        }

        void expect(int n) {
            if (items.size() != n + 1) {
                throw new CaseError("operation " + index + ": `" + name() + "` takes " + n + " arguments, got " + (items.size() - 1));
            }
        }

        String what(int i) {
            return "operation " + index + "'s argument " + i;
        }

        int number(int i) {
            return Args.asInt(items.get(i), what(i));
        }

        /** A number from `low` to `high`, both included. */
        int within(int i, int low, int high) {
            int n = number(i);
            if (n < low || n > high) {
                throw new CaseError(what(i) + " must be from " + low + " to " + high);
            }
            return n;
        }

        BlockState state(int i) {
            return byId(items.get(i), what(i));
        }

        Heightmap.Types kind(int i) {
            return KINDS[within(i, 0, KINDS.length - 1)];
        }
    }

    private static BlockState byId(JsonElement item, String what) {
        int id = Args.asInt(item, what);
        BlockState state = id >= 0 ? Block.BLOCK_STATE_REGISTRY.byId(id) : null;
        if (state == null) {
            throw new CaseError(what + " must be a block state ID, from 0 to " + (Block.BLOCK_STATE_REGISTRY.size() - 1));
        }
        return state;
    }

    // getHighestSectionPosition is marked for removal, but primeHeightmaps starts from it.
    @Override
    @SuppressWarnings("removal")
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        if (!blobs.isEmpty()) {
            throw new CaseError("`chunk` takes no blobs");
        }
        int minY = Args.asInt(Args.field(input, "min_y"), "`min_y`");
        int sections = Args.asInt(Args.field(input, "sections"), "`sections`");
        if ((minY & 15) != 0 || minY < -2032 || sections < 1 || minY + sections * 16 > 2032) {
            throw new CaseError("`min_y` must be a multiple of 16 and the sections inside -2032 to 2032");
        }
        JsonArray ops = Args.array(input, "ops");
        PalettedContainerFactory containers = PalettedContainerFactory.create(RegistriesProbe.access());
        ProtoChunk chunk = new ProtoChunk(new ChunkPos(0, 0), UpgradeData.EMPTY, LevelHeightAccessor.create(minY, sections * 16), containers, null);
        for (Heightmap.Types kind : KINDS) {
            chunk.getOrCreateHeightmapUnprimed(kind);
        }
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        int top = minY + sections * 16 - 1;
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            Op op = new Op(ops.get(k).getAsJsonArray(), k);
            switch (op.name()) {
                case "set" -> {
                    op.expect(4);
                    BlockState old = set(chunk, op.within(1, 0, 15), op.within(2, minY, top), op.within(3, 0, 15), op.state(4));
                    out.writeInt(old == null ? -1 : Block.BLOCK_STATE_REGISTRY.getId(old));
                }
                case "fill" -> {
                    // Every block from one corner to the other, y, then x, then z.
                    op.expect(7);
                    int x0 = op.within(1, 0, 15), y0 = op.within(2, minY, top), z0 = op.within(3, 0, 15);
                    int x1 = op.within(4, x0, 15), y1 = op.within(5, y0, top), z1 = op.within(6, z0, 15);
                    BlockState state = op.state(7);
                    for (int y = y0; y <= y1; y++) {
                        for (int x = x0; x <= x1; x++) {
                            for (int z = z0; z <= z1; z++) {
                                set(chunk, x, y, z, state);
                            }
                        }
                    }
                }
                case "random_sets" -> {
                    // `count` states from the list, each at a column and a height from `low` to
                    // `high`; it gives how many changed a block.
                    op.expect(5);
                    Draws draws = new Draws(Args.parseLong(Args.asString(op.items().get(1), op.what(1)), op.what(1)));
                    int count = op.within(2, 0, 1 << 20);
                    if (!op.items().get(3).isJsonArray() || op.items().get(3).getAsJsonArray().isEmpty()) {
                        throw new CaseError(op.what(3) + " must be a non-empty array of block state IDs");
                    }
                    JsonArray list = op.items().get(3).getAsJsonArray();
                    BlockState[] states = new BlockState[list.size()];
                    for (int i = 0; i < states.length; i++) {
                        states[i] = byId(list.get(i), op.what(3) + "'s entry " + i);
                    }
                    int low = op.within(4, minY, top);
                    int high = op.within(5, low, top);
                    int changed = 0;
                    for (int n = 0; n < count; n++) {
                        int x = draws.next() % 16;
                        int z = draws.next() % 16;
                        int y = low + draws.next() % (high - low + 1);
                        if (set(chunk, x, y, z, states[draws.next() % states.length]) != null) {
                            changed++;
                        }
                    }
                    out.writeInt(changed);
                }
                case "block" -> {
                    op.expect(3);
                    BlockState state = chunk.getBlockState(new BlockPos(op.within(1, 0, 15), op.within(2, minY, top), op.within(3, 0, 15)));
                    out.writeInt(Block.BLOCK_STATE_REGISTRY.getId(state));
                }
                case "update" -> {
                    // A heightmap told of a state set at a place, as generation tells the `_WG` ones.
                    op.expect(5);
                    boolean changed = chunk.getOrCreateHeightmapUnprimed(op.kind(1))
                        .update(op.within(2, 0, 15), op.within(3, minY, top), op.within(4, 0, 15), op.state(5));
                    out.writeByte(changed ? 1 : 0);
                }
                case "prime" -> {
                    op.expect(1);
                    if (!op.items().get(1).isJsonArray()) {
                        throw new CaseError(op.what(1) + " must be an array of heightmap IDs");
                    }
                    EnumSet<Heightmap.Types> kinds = EnumSet.noneOf(Heightmap.Types.class);
                    for (JsonElement item : op.items().get(1).getAsJsonArray()) {
                        int id = Args.asInt(item, op.what(1) + "'s entry");
                        if (id < 0 || id >= KINDS.length) {
                            throw new CaseError(op.what(1) + "'s entries must be from 0 to " + (KINDS.length - 1));
                        }
                        kinds.add(KINDS[id]);
                    }
                    Heightmap.primeHeightmaps(chunk, kinds);
                }
                case "heightmap" -> {
                    op.expect(1);
                    long[] longs = chunk.getOrCreateHeightmapUnprimed(op.kind(1)).getRawData();
                    out.writeInt(longs.length);
                    for (long l : longs) {
                        out.writeLong(l);
                    }
                }
                case "highest" -> {
                    op.expect(0);
                    out.writeInt(chunk.getHighestSectionPosition());
                }
                case "counts" -> {
                    op.expect(0);
                    for (LevelChunkSection section : chunk.getSections()) {
                        for (Field f : COUNTS) {
                            try {
                                out.writeInt(f.getShort(section));
                            } catch (IllegalAccessException e) {
                                throw new IllegalStateException(e);
                            }
                        }
                    }
                }
                case "recount" -> {
                    op.expect(0);
                    for (LevelChunkSection section : chunk.getSections()) {
                        section.recalcBlockCounts();
                    }
                }
                case "write" -> {
                    op.expect(0);
                    FriendlyByteBuf buf = new FriendlyByteBuf(Unpooled.buffer());
                    for (LevelChunkSection section : chunk.getSections()) {
                        section.write(buf);
                    }
                    byte[] sent = new byte[buf.readableBytes()];
                    buf.readBytes(sent);
                    out.writeInt(sent.length);
                    out.write(sent);
                }
                default -> throw new CaseError("operation " + k + ": unknown `" + op.name() + "`");
            }
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    /** What {@code LevelChunk.setBlockState} does to the sections and heightmaps. */
    private static BlockState set(ProtoChunk chunk, int x, int y, int z, BlockState state) {
        LevelChunkSection section = chunk.getSection(chunk.getSectionIndex(y));
        if (section.hasOnlyAir() && state.isAir()) {
            return null;
        }
        BlockState old = section.setBlockState(x, y & 15, z, state);
        if (old == state) {
            return null;
        }
        for (Heightmap.Types kind : KEPT) {
            chunk.getOrCreateHeightmapUnprimed(kind).update(x, y, z, state);
        }
        return old;
    }
}
