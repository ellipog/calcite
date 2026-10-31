package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.network.protocol.game.ClientboundLightUpdatePacketData;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.LightLayer;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.DataLayer;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.level.chunk.LightChunk;
import net.minecraft.world.level.chunk.LightChunkGetter;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.lighting.LevelLightEngine;
import net.minecraft.world.level.lighting.LightEngine;
import net.minecraft.world.level.material.FluidState;

/**
 * `light`: vanilla's light engines, {@code LevelLightEngine} with its block and sky engines, over
 * chunks the case makes, run by a list of operations, each result written to one blob
 * (rig/PROTOCOL.md).
 *
 * <p>The chunks are {@code ProtoChunk}s, each with its own {@code ChunkSkyLightSources}, and the
 * engine gets them from a {@code LightChunkGetter} over a map, as a level's chunk source gives the
 * chunks it has. {@code fill} and {@code random} with nothing told set blocks as generation does
 * before light; {@code set} does what {@code LevelChunk.setBlockState} does for light once it's set
 * a block. The rest call the engine as {@code ThreadedLevelLightEngine} does.
 */
final class LightProbe implements Probe {
    @Override
    public String name() {
        return "light";
    }

    @Override
    public int version() {
        return 1;
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

        /** A number from `low` to `high`, both included. */
        int within(int i, int low, int high) {
            int n = Args.asInt(items.get(i), what(i));
            if (n < low || n > high) {
                throw new CaseError(what(i) + " must be from " + low + " to " + high);
            }
            return n;
        }

        boolean flag(int i) {
            return within(i, 0, 1) == 1;
        }

        BlockState state(int i) {
            return byId(items.get(i), what(i));
        }

        long seed(int i) {
            return Args.parseLong(Args.asString(items.get(i), what(i)), what(i));
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

    // How far from 0 a chunk may be, each way.
    private static final int CHUNKS = 1000;

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        if (!blobs.isEmpty()) {
            throw new CaseError("`light` takes no blobs");
        }
        int minY = Args.asInt(Args.field(input, "min_y"), "`min_y`");
        int sections = Args.asInt(Args.field(input, "sections"), "`sections`");
        if ((minY & 15) != 0 || minY < -2032 || sections < 1 || minY + sections * 16 > 2032) {
            throw new CaseError("`min_y` must be a multiple of 16 and the sections inside -2032 to 2032");
        }
        int skyFlag = Args.asInt(Args.field(input, "sky"), "`sky`");
        if (skyFlag != 0 && skyFlag != 1) {
            throw new CaseError("`sky` must be 0 or 1");
        }
        JsonArray ops = Args.array(input, "ops");
        LevelHeightAccessor height = LevelHeightAccessor.create(minY, sections * 16);
        PalettedContainerFactory containers = PalettedContainerFactory.create(RegistriesProbe.access());
        Long2ObjectOpenHashMap<ProtoChunk> chunks = new Long2ObjectOpenHashMap<>();
        BlockGetter level = new BlockGetter() {
            @Override
            public BlockEntity getBlockEntity(BlockPos pos) {
                return null;
            }

            @Override
            public BlockState getBlockState(BlockPos pos) {
                ProtoChunk chunk = chunks.get(ChunkPos.pack(pos));
                return chunk == null ? Blocks.AIR.defaultBlockState() : chunk.getBlockState(pos);
            }

            @Override
            public FluidState getFluidState(BlockPos pos) {
                return getBlockState(pos).getFluidState();
            }

            @Override
            public int getHeight() {
                return height.getHeight();
            }

            @Override
            public int getMinY() {
                return height.getMinY();
            }
        };
        LightChunkGetter getter = new LightChunkGetter() {
            @Override
            public LightChunk getChunkForLighting(int x, int z) {
                return chunks.get(ChunkPos.pack(x, z));
            }

            @Override
            public BlockGetter getLevel() {
                return level;
            }
        };
        LevelLightEngine engine = new LevelLightEngine(getter, true, skyFlag == 1);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        int top = minY + sections * 16 - 1;
        int minSection = minY >> 4;
        int maxSection = minSection + sections - 1;
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            Op op = new Op(ops.get(k).getAsJsonArray(), k);
            switch (op.name()) {
                case "chunk" -> {
                    op.expect(2);
                    int cx = op.within(1, -CHUNKS, CHUNKS), cz = op.within(2, -CHUNKS, CHUNKS);
                    if (chunks.containsKey(ChunkPos.pack(cx, cz))) {
                        throw new CaseError("operation " + k + ": there's a chunk at " + cx + ", " + cz + " already");
                    }
                    chunks.put(ChunkPos.pack(cx, cz), new ProtoChunk(new ChunkPos(cx, cz), UpgradeData.EMPTY, height, containers, null));
                }
                case "fill" -> {
                    // Every block from one corner to the other, y, then x, then z, with nothing told.
                    op.expect(7);
                    int x0 = op.within(1, -CHUNKS * 16, CHUNKS * 16 + 15), y0 = op.within(2, minY, top), z0 = op.within(3, -CHUNKS * 16, CHUNKS * 16 + 15);
                    int x1 = op.within(4, x0, x0 + 255), y1 = op.within(5, y0, top), z1 = op.within(6, z0, z0 + 255);
                    BlockState state = op.state(7);
                    for (int y = y0; y <= y1; y++) {
                        for (int x = x0; x <= x1; x++) {
                            for (int z = z0; z <= z1; z++) {
                                put(chunk(chunks, k, x, z), x, y, z, state);
                            }
                        }
                    }
                }
                case "random" -> {
                    // `count` states from the list, each at a block in the box, set with nothing
                    // told or as `LevelChunk` sets it, by `tell`.
                    op.expect(10);
                    boolean tell = op.flag(1);
                    Draws draws = new Draws(op.seed(2));
                    int count = op.within(3, 0, 1 << 20);
                    if (!op.items().get(4).isJsonArray() || op.items().get(4).getAsJsonArray().isEmpty()) {
                        throw new CaseError(op.what(4) + " must be a non-empty array of block state IDs");
                    }
                    JsonArray list = op.items().get(4).getAsJsonArray();
                    BlockState[] states = new BlockState[list.size()];
                    for (int i = 0; i < states.length; i++) {
                        states[i] = byId(list.get(i), op.what(4) + "'s entry " + i);
                    }
                    int x0 = op.within(5, -CHUNKS * 16, CHUNKS * 16 + 15), y0 = op.within(6, minY, top), z0 = op.within(7, -CHUNKS * 16, CHUNKS * 16 + 15);
                    int x1 = op.within(8, x0, x0 + 255), y1 = op.within(9, y0, top), z1 = op.within(10, z0, z0 + 255);
                    for (int n = 0; n < count; n++) {
                        int x = x0 + draws.next() % (x1 - x0 + 1);
                        int y = y0 + draws.next() % (y1 - y0 + 1);
                        int z = z0 + draws.next() % (z1 - z0 + 1);
                        BlockState state = states[draws.next() % states.length];
                        ProtoChunk chunk = chunk(chunks, k, x, z);
                        if (tell) {
                            set(engine, chunk, x, y, z, state);
                        } else {
                            put(chunk, x, y, z, state);
                        }
                    }
                }
                case "set" -> {
                    op.expect(4);
                    int x = op.within(1, -CHUNKS * 16, CHUNKS * 16 + 15), y = op.within(2, minY, top), z = op.within(3, -CHUNKS * 16, CHUNKS * 16 + 15);
                    BlockState old = set(engine, chunk(chunks, k, x, z), x, y, z, op.state(4));
                    out.writeInt(old == null ? -1 : Block.BLOCK_STATE_REGISTRY.getId(old));
                }
                case "sources" -> {
                    // `initializeLightSources`, as the INITIALIZE_LIGHT status does first.
                    op.expect(2);
                    int cx = op.within(1, -CHUNKS, CHUNKS), cz = op.within(2, -CHUNKS, CHUNKS);
                    chunk(chunks, k, cx * 16, cz * 16).initializeLightSources();
                }
                case "sections" -> {
                    // What `ThreadedLevelLightEngine.initializeLight` tells first: each section
                    // with a block that isn't air.
                    op.expect(2);
                    int cx = op.within(1, -CHUNKS, CHUNKS), cz = op.within(2, -CHUNKS, CHUNKS);
                    ProtoChunk chunk = chunk(chunks, k, cx * 16, cz * 16);
                    LevelChunkSection[] all = chunk.getSections();
                    for (int i = 0; i < chunk.getSectionsCount(); i++) {
                        if (!all[i].hasOnlyAir()) {
                            engine.updateSectionStatus(SectionPos.of(cx, height.getSectionYFromSectionIndex(i), cz), false);
                        }
                    }
                }
                case "status" -> {
                    op.expect(4);
                    SectionPos pos = SectionPos.of(op.within(1, -CHUNKS, CHUNKS), op.within(2, minSection - 1, maxSection + 1), op.within(3, -CHUNKS, CHUNKS));
                    engine.updateSectionStatus(pos, op.flag(4));
                }
                case "enable" -> {
                    op.expect(3);
                    engine.setLightEnabled(new ChunkPos(op.within(1, -CHUNKS, CHUNKS), op.within(2, -CHUNKS, CHUNKS)), op.flag(3));
                }
                case "retain" -> {
                    op.expect(3);
                    engine.retainData(new ChunkPos(op.within(1, -CHUNKS, CHUNKS), op.within(2, -CHUNKS, CHUNKS)), op.flag(3));
                }
                case "propagate" -> {
                    op.expect(2);
                    engine.propagateLightSources(new ChunkPos(op.within(1, -CHUNKS, CHUNKS), op.within(2, -CHUNKS, CHUNKS)));
                }
                case "check" -> {
                    op.expect(3);
                    engine.checkBlock(new BlockPos(op.within(1, -CHUNKS * 16, CHUNKS * 16 + 15), op.within(2, minY - 16, top + 16), op.within(3, -CHUNKS * 16, CHUNKS * 16 + 15)));
                }
                case "queue" -> {
                    // Light for a section, as a save gives it: none, a layer of one level, or
                    // 2048 bytes drawn from a seed.
                    op.expect(6);
                    LightLayer layer = op.flag(1) ? LightLayer.SKY : LightLayer.BLOCK;
                    SectionPos pos = SectionPos.of(op.within(2, -CHUNKS, CHUNKS), op.within(3, minSection - 1, maxSection + 1), op.within(4, -CHUNKS, CHUNKS));
                    DataLayer data = switch (op.within(5, 0, 2)) {
                        case 0 -> null;
                        case 1 -> new DataLayer(op.within(6, 0, 15));
                        default -> {
                            Draws draws = new Draws(op.seed(6));
                            byte[] b = new byte[2048];
                            for (int i = 0; i < b.length; i++) {
                                b[i] = (byte) draws.next();
                            }
                            yield new DataLayer(b);
                        }
                    };
                    engine.queueSectionData(layer, pos, data);
                }
                case "run" -> {
                    op.expect(0);
                    out.writeInt(engine.runLightUpdates());
                }
                case "work" -> {
                    op.expect(0);
                    out.writeByte(engine.hasLightWork() ? 1 : 0);
                }
                case "on" -> {
                    op.expect(2);
                    out.writeByte(engine.lightOnInColumn(SectionPos.getZeroNode(op.within(1, -CHUNKS, CHUNKS), op.within(2, -CHUNKS, CHUNKS))) ? 1 : 0);
                }
                case "value" -> {
                    op.expect(4);
                    LightLayer layer = op.flag(1) ? LightLayer.SKY : LightLayer.BLOCK;
                    BlockPos pos = new BlockPos(op.within(2, -CHUNKS * 16, CHUNKS * 16 + 15), op.within(3, minY - 64, top + 64), op.within(4, -CHUNKS * 16, CHUNKS * 16 + 15));
                    out.writeByte(engine.getLayerListener(layer).getLightValue(pos));
                }
                case "layer" -> {
                    // A section's light as a packet takes it: 0 for none, 1 for an empty layer,
                    // or 2 and its bytes.
                    op.expect(4);
                    LightLayer layer = op.flag(1) ? LightLayer.SKY : LightLayer.BLOCK;
                    SectionPos pos = SectionPos.of(op.within(2, -CHUNKS, CHUNKS), op.within(3, minSection - 1, maxSection + 1), op.within(4, -CHUNKS, CHUNKS));
                    DataLayer data = engine.getLayerListener(layer).getDataLayerData(pos);
                    if (data == null) {
                        out.writeByte(0);
                    } else if (data.isEmpty()) {
                        out.writeByte(1);
                    } else {
                        out.writeByte(2);
                        out.write(data.copy().getData());
                    }
                }
                case "light" -> {
                    // The chunk's light as `level_chunk_with_light` sends it.
                    op.expect(2);
                    ChunkPos pos = new ChunkPos(op.within(1, -CHUNKS, CHUNKS), op.within(2, -CHUNKS, CHUNKS));
                    ClientboundLightUpdatePacketData data = new ClientboundLightUpdatePacketData(pos, engine, null, null);
                    ByteBuf buf = Unpooled.buffer();
                    ClientboundLightUpdatePacketData.STREAM_CODEC.encode(buf, data);
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

    private static ProtoChunk chunk(Long2ObjectOpenHashMap<ProtoChunk> chunks, int k, int x, int z) {
        ProtoChunk chunk = chunks.get(ChunkPos.pack(x >> 4, z >> 4));
        if (chunk == null) {
            throw new CaseError("operation " + k + ": there's no chunk at " + (x >> 4) + ", " + (z >> 4));
        }
        return chunk;
    }

    /**
     * A block set with nothing told, as generation sets them before light. As {@code LevelChunk},
     * air isn't set in a section of only air, so the section holds what it would in the world.
     */
    private static void put(ProtoChunk chunk, int x, int y, int z, BlockState state) {
        LevelChunkSection section = chunk.getSection(chunk.getSectionIndex(y));
        if (!(section.hasOnlyAir() && state.isAir())) {
            section.setBlockState(x & 15, y & 15, z & 15, state);
        }
    }

    /** What {@code LevelChunk.setBlockState} does for light: it gives the old state, or null if nothing changed. */
    private static BlockState set(LevelLightEngine engine, ProtoChunk chunk, int x, int y, int z, BlockState state) {
        LevelChunkSection section = chunk.getSection(chunk.getSectionIndex(y));
        boolean wasEmpty = section.hasOnlyAir();
        if (wasEmpty && state.isAir()) {
            return null;
        }
        BlockState old = section.setBlockState(x & 15, y & 15, z & 15, state);
        if (old == state) {
            return null;
        }
        boolean isEmpty = section.hasOnlyAir();
        BlockPos pos = new BlockPos(x, y, z);
        if (wasEmpty != isEmpty) {
            engine.updateSectionStatus(pos, isEmpty);
        }
        if (LightEngine.hasDifferentLightProperties(old, state)) {
            chunk.getSkyLightSources().update(chunk, x & 15, y, z & 15);
            engine.checkBlock(pos);
        }
        return old;
    }
}
