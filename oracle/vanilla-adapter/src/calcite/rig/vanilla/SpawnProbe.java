package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.dedicated.DedicatedServer;
import net.minecraft.server.level.PlayerSpawnFinder;
import net.minecraft.server.level.ServerChunkCache;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.CollisionGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.border.WorldBorder;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.status.ChunkStatus;
import net.minecraft.world.level.dimension.BuiltinDimensionTypes;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.VoxelShape;

/**
 * `spawn`: where vanilla's {@code PlayerSpawnFinder} puts a player new to the world, over chunks
 * the case makes, run by a list of operations, each result written to one blob (rig/PROTOCOL.md).
 *
 * <p>The chunks are {@code LevelChunk}s of the overworld's height, in a stand-in for the
 * overworld's {@code ServerLevel}, made without its constructor, whose chunk source adds a ticket
 * by noting it, every chunk the case has being full, and whose server runs a task at once. So a
 * search runs vanilla's own walk, checks and fallback, a candidate at a time, as the server's
 * thread would once each candidate's chunk is loaded; only its random offset is the case's, set
 * in the finder after its constructor draws one. Blocks are set as {@code LevelChunk.setBlockState}
 * sets them in the section and the heightmaps, with nothing else told. No entity collides.
 */
final class SpawnProbe implements Probe {
    @Override
    public String name() {
        return "spawn";
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

        int within(int i, int low, int high) {
            int n = Args.asInt(items.get(i), what(i));
            if (n < low || n > high) {
                throw new CaseError(what(i) + " must be from " + low + " to " + high);
            }
            return n;
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

    /** The overworld, as far as the spawn finder asks: its chunks, its height and its tickets. */
    private static final class Level extends ServerLevel {
        Long2ObjectOpenHashMap<LevelChunk> chunks;
        Source source;
        MinecraftServer server;
        DimensionType type;
        PalettedContainerFactory containers;
        WorldBorder border;

        // Never run: the level is made with `Unsafe.allocateInstance`.
        private Level() {
            super(null, null, null, null, null, null, false, 0L, null, false);
        }

        @Override
        public LevelChunk getChunk(int chunkX, int chunkZ) {
            return chunks.get(ChunkPos.pack(chunkX, chunkZ));
        }

        @Override
        public ChunkAccess getChunk(int chunkX, int chunkZ, ChunkStatus status, boolean loadOrGenerate) {
            return chunks.get(ChunkPos.pack(chunkX, chunkZ));
        }

        @Override
        public DimensionType dimensionType() {
            return type;
        }

        @Override
        public PalettedContainerFactory palettedContainerFactory() {
            return containers;
        }

        @Override
        public ServerChunkCache getChunkSource() {
            return source;
        }

        @Override
        public MinecraftServer getServer() {
            return server;
        }

        @Override
        public WorldBorder getWorldBorder() {
            return border;
        }

        @Override
        public List<VoxelShape> getEntityCollisions(Entity source, AABB testArea) {
            return List.of();
        }
    }

    /** The chunk source, which notes each ticket a search adds, and has its chunk full at once. */
    private static final class Source extends ServerChunkCache {
        Level level;
        List<ChunkPos> tickets;

        // Never run, as the level's.
        private Source() {
            super(null, null, null, null, null, null, 0, 0, false, null);
        }

        @Override
        public CompletableFuture<?> addTicketAndLoadWithRadius(TicketType type, ChunkPos pos, int radius) {
            if (type != TicketType.SPAWN_SEARCH || radius != 0) {
                throw new CaseError("the search added a ticket " + type + " of radius " + radius);
            }
            if (!level.chunks.containsKey(pos.pack())) {
                throw new CaseError("the search's candidate in chunk " + pos.x() + ", " + pos.z() + " isn't in a chunk the case made");
            }
            tickets.add(pos);
            return CompletableFuture.completedFuture(null);
        }
    }

    /**
     * The server, which keeps what's handed to it for its thread to run in turn, as its thread
     * would once each candidate's chunk is full: one at a time, so a search through a thousand
     * candidates doesn't run each inside the last.
     */
    private static final class Server extends DedicatedServer {
        ArrayDeque<Runnable> tasks;

        // Never run, as the level's.
        private Server() {
            super(null, null, null, null, null, null, null, null, null, null);
        }

        @Override
        public void execute(Runnable command) {
            tasks.add(command);
        }

        void runAll() {
            Runnable task;
            while ((task = tasks.poll()) != null) {
                task.run();
            }
        }
    }

    // How far from 0 a chunk may be, each way.
    private static final int CHUNKS = 1000;

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`spawn` takes no blobs");
        }
        JsonArray ops = Args.array(input, "ops");
        Level level = (Level) allocate(Level.class);
        level.chunks = new Long2ObjectOpenHashMap<>();
        level.type = RegistriesProbe.access().lookupOrThrow(Registries.DIMENSION_TYPE).getOrThrow(BuiltinDimensionTypes.OVERWORLD).value();
        level.containers = PalettedContainerFactory.create(RegistriesProbe.access());
        level.border = new WorldBorder();
        level.source = (Source) allocate(Source.class);
        level.source.level = level;
        level.source.tickets = new ArrayList<>();
        Server server = (Server) allocate(Server.class);
        server.tasks = new ArrayDeque<>();
        level.server = server;
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        int minY = level.getMinY();
        int top = level.getMaxY();
        int low = -CHUNKS * 16;
        int high = CHUNKS * 16 + 15;
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            Op op = new Op(ops.get(k).getAsJsonArray(), k);
            switch (op.name()) {
                case "chunk" -> {
                    op.expect(2);
                    int cx = op.within(1, -CHUNKS, CHUNKS), cz = op.within(2, -CHUNKS, CHUNKS);
                    if (level.chunks.containsKey(ChunkPos.pack(cx, cz))) {
                        throw new CaseError("operation " + k + ": there's a chunk at " + cx + ", " + cz + " already");
                    }
                    level.chunks.put(ChunkPos.pack(cx, cz), new LevelChunk(level, new ChunkPos(cx, cz)));
                }
                case "fill" -> {
                    // Every block from one corner to the other, y, then x, then z.
                    op.expect(7);
                    int x0 = op.within(1, low, high), y0 = op.within(2, minY, top), z0 = op.within(3, low, high);
                    int x1 = op.within(4, x0, x0 + 255), y1 = op.within(5, y0, top), z1 = op.within(6, z0, z0 + 255);
                    BlockState state = op.state(7);
                    for (int y = y0; y <= y1; y++) {
                        for (int x = x0; x <= x1; x++) {
                            for (int z = z0; z <= z1; z++) {
                                put(chunk(level, k, x, z), x, y, z, state);
                            }
                        }
                    }
                }
                case "random" -> {
                    // `count` states from the list, each at a block in the box.
                    op.expect(9);
                    Draws draws = new Draws(op.seed(1));
                    int count = op.within(2, 0, 1 << 20);
                    if (!op.items().get(3).isJsonArray() || op.items().get(3).getAsJsonArray().isEmpty()) {
                        throw new CaseError(op.what(3) + " must be a non-empty array of block state IDs");
                    }
                    JsonArray list = op.items().get(3).getAsJsonArray();
                    BlockState[] states = new BlockState[list.size()];
                    for (int i = 0; i < states.length; i++) {
                        states[i] = byId(list.get(i), op.what(3) + "'s entry " + i);
                    }
                    int x0 = op.within(4, low, high), y0 = op.within(5, minY, top), z0 = op.within(6, low, high);
                    int x1 = op.within(7, x0, x0 + 255), y1 = op.within(8, y0, top), z1 = op.within(9, z0, z0 + 255);
                    for (int n = 0; n < count; n++) {
                        int x = x0 + draws.next() % (x1 - x0 + 1);
                        int y = y0 + draws.next() % (y1 - y0 + 1);
                        int z = z0 + draws.next() % (z1 - z0 + 1);
                        BlockState state = states[draws.next() % states.length];
                        put(chunk(level, k, x, z), x, y, z, state);
                    }
                }
                case "respawn" -> {
                    // `getLevelRespawnPos`: a byte 0 for none, or 1 and the block's x, y and z.
                    op.expect(2);
                    int x = op.within(1, low, high), z = op.within(2, low, high);
                    chunk(level, k, x, z);
                    BlockPos pos = (BlockPos) call("getLevelRespawnPos", new Class<?>[] {ServerLevel.class, int.class, int.class}, level, x, z);
                    if (pos == null) {
                        out.writeByte(0);
                    } else {
                        out.writeByte(1);
                        out.writeInt(pos.getX());
                        out.writeInt(pos.getY());
                        out.writeInt(pos.getZ());
                    }
                }
                case "fits" -> {
                    // `noCollisionNoLiquid`: a byte.
                    op.expect(3);
                    BlockPos pos = new BlockPos(op.within(1, low, high), op.within(2, minY - 64, top + 64), op.within(3, low, high));
                    boolean fits = (Boolean) call("noCollisionNoLiquid", new Class<?>[] {CollisionGetter.class, BlockPos.class}, level, pos);
                    out.writeByte(fits ? 1 : 0);
                }
                case "fixup" -> {
                    // `fixupSpawnHeight`, as an adventure world's spawn: the place's x, y and z.
                    op.expect(3);
                    BlockPos pos = new BlockPos(op.within(1, low, high), op.within(2, minY - 64, top + 64), op.within(3, low, high));
                    vec(out, (Vec3) call("fixupSpawnHeight", new Class<?>[] {CollisionGetter.class, BlockPos.class}, level, pos));
                }
                case "search" -> {
                    // A whole search from `offset`: the tickets it added, an `int` count and each
                    // chunk's x and z, then the place's x, y and z.
                    op.expect(5);
                    BlockPos origin = new BlockPos(op.within(1, low, high), op.within(2, minY - 64, top + 64), op.within(3, low, high));
                    int radius = op.within(4, 0, 64);
                    long side = radius * 2L + 1L;
                    int count = (int) Math.min(1024L, side * side);
                    int offset = op.within(5, 0, count - 1);
                    Vec3 place = search(level, origin, radius, offset);
                    List<ChunkPos> tickets = level.source.tickets;
                    out.writeInt(tickets.size());
                    for (ChunkPos pos : tickets) {
                        out.writeInt(pos.x());
                        out.writeInt(pos.z());
                    }
                    tickets.clear();
                    vec(out, place);
                }
                default -> throw new CaseError("operation " + k + ": unknown `" + op.name() + "`");
            }
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    private static Vec3 search(Level level, BlockPos origin, int radius, int offset) throws Exception {
        Constructor<PlayerSpawnFinder> make = PlayerSpawnFinder.class.getDeclaredConstructor(ServerLevel.class, BlockPos.class, int.class);
        make.setAccessible(true);
        PlayerSpawnFinder finder = make.newInstance(level, origin, radius);
        Field drawn = PlayerSpawnFinder.class.getDeclaredField("offset");
        drawn.setAccessible(true);
        drawn.setInt(finder, offset);
        Method next = PlayerSpawnFinder.class.getDeclaredMethod("scheduleNext");
        next.setAccessible(true);
        try {
            next.invoke(finder);
        } catch (InvocationTargetException e) {
            throw unwrap(e);
        }
        ((Server) level.server).runAll();
        Field done = PlayerSpawnFinder.class.getDeclaredField("finishedFuture");
        done.setAccessible(true);
        CompletableFuture<?> future = (CompletableFuture<?>) done.get(finder);
        if (!future.isDone()) {
            throw new IllegalStateException("the search didn't finish");
        }
        try {
            return (Vec3) future.join();
        } catch (CompletionException e) {
            // A case's error, as a candidate outside its chunks, comes in a crash report.
            for (Throwable cause = e; cause != null; cause = cause.getCause()) {
                if (cause instanceof CaseError error) {
                    throw error;
                }
            }
            throw e;
        }
    }

    private static Object call(String name, Class<?>[] types, Object... args) throws Exception {
        Method m = PlayerSpawnFinder.class.getDeclaredMethod(name, types);
        m.setAccessible(true);
        try {
            return m.invoke(null, args);
        } catch (InvocationTargetException e) {
            throw unwrap(e);
        }
    }

    private static Exception unwrap(InvocationTargetException e) {
        Throwable cause = e.getCause();
        if (cause instanceof RuntimeException r) {
            return r;
        }
        if (cause instanceof Error error) {
            throw error;
        }
        return e;
    }

    private static void vec(DataOutputStream out, Vec3 v) throws IOException {
        out.writeDouble(v.x);
        out.writeDouble(v.y);
        out.writeDouble(v.z);
    }

    private static LevelChunk chunk(Level level, int k, int x, int z) {
        LevelChunk chunk = level.chunks.get(ChunkPos.pack(x >> 4, z >> 4));
        if (chunk == null) {
            throw new CaseError("operation " + k + ": there's no chunk at " + (x >> 4) + ", " + (z >> 4));
        }
        return chunk;
    }

    /** A block set as {@code LevelChunk.setBlockState} sets it in its section and heightmaps. */
    private static void put(LevelChunk chunk, int x, int y, int z, BlockState state) {
        LevelChunkSection section = chunk.getSection(chunk.getSectionIndex(y));
        if (section.hasOnlyAir() && state.isAir()) {
            return;
        }
        BlockState old = section.setBlockState(x & 15, y & 15, z & 15, state);
        if (old == state) {
            return;
        }
        for (Map.Entry<Heightmap.Types, Heightmap> e : chunk.getHeightmaps()) {
            e.getValue().update(x & 15, y, z & 15, state);
        }
    }

    private static Object allocate(Class<?> type) throws Exception {
        // `sun.misc.Unsafe`, found by name, since the build takes no warnings.
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field theUnsafe = unsafeClass.getDeclaredField("theUnsafe");
        theUnsafe.setAccessible(true);
        Method allocate = unsafeClass.getMethod("allocateInstance", Class.class);
        return allocate.invoke(theUnsafe.get(null), type);
    }
}
