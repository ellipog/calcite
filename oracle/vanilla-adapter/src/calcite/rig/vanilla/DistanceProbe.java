package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import it.unimi.dsi.fastutil.longs.Long2ByteMap;
import it.unimi.dsi.fastutil.longs.Long2IntMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectLinkedOpenHashMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import it.unimi.dsi.fastutil.longs.LongIterator;
import it.unimi.dsi.fastutil.longs.LongOpenHashSet;
import it.unimi.dsi.fastutil.longs.LongSet;
import it.unimi.dsi.fastutil.objects.ObjectIterator;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Queue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import net.minecraft.core.SectionPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.server.level.ChunkHolder;
import net.minecraft.server.level.ChunkLevel;
import net.minecraft.server.level.ChunkMap;
import net.minecraft.server.level.ChunkResult;
import net.minecraft.server.level.DistanceManager;
import net.minecraft.server.level.FullChunkStatus;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.Ticket;
import net.minecraft.server.level.TicketType;
import net.minecraft.util.TriState;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.TicketStorage;
import net.minecraft.world.level.chunk.LevelChunk;

/**
 * `distance`: vanilla's own {@link DistanceManager}, with its trackers, its player ticket
 * dispatcher and its {@link TicketStorage}, through a list of operations, and its whole state
 * dumped where the case says.
 *
 * <p>Its two executors are queues the case runs by hand: the dispatcher's worker, which runs the
 * dispatcher's jobs one at a time, and the main thread. So the case says when each job and task
 * runs, as the threads do in a server, and vanilla runs the same way every time. The holders whose
 * level changed are kept in a {@link LinkedHashSet} in place of vanilla's set of identities, whose
 * order is different every run, so they're updated in the order their levels changed, as Calcite
 * updates them.
 *
 * <p>The holders are {@link ChunkMap}'s part, which the manager leaves to its subclass: this one
 * keeps them as {@code ChunkMap} does, its {@code updateChunkScheduling}, {@code processUnloads}
 * and {@code promoteChunkMap} copied, with each unload queued at once, as a holder whose saves are
 * done has it queued. The holders are vanilla's {@link ChunkHolder}, with their futures cut down
 * to the chunk ticking its entities, which the case says is ready, and no worldgen or light.
 */
final class DistanceProbe implements Probe {
    @Override
    public String name() {
        return "distance";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`distance` takes no blobs");
        }
        JsonArray ops = Args.array(input, "ops");
        ArrayDeque<Runnable> worker = new ArrayDeque<>();
        ArrayDeque<Runnable> main = new ArrayDeque<>();
        TicketStorage storage = new TicketStorage();
        Manager manager = new Manager(storage, worker::add, main::add);
        Field changed = DistanceManager.class.getDeclaredField("chunksToUpdateFutures");
        changed.setAccessible(true);
        changed.set(manager, new LinkedHashSet<ChunkHolder>());
        ChunkMap map = (ChunkMap) allocate(ChunkMap.class);
        Field updating = ChunkMap.class.getDeclaredField("updatingChunkMap");
        updating.setAccessible(true);
        updating.set(map, manager.updating);
        Map<Integer, ServerPlayer> players = new HashMap<>();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            JsonArray op = ops.get(k).getAsJsonArray();
            String name = Args.asString(op.get(0), "operation " + k + "'s name");
            switch (name) {
                case "player" -> {
                    expect(op, k, 3);
                    ServerPlayer player = players.get(integer(op, k, 1));
                    if (player == null) {
                        // A player's hash is its entity ID, which can't be 0.
                        player = (ServerPlayer) allocate(ServerPlayer.class);
                        Field id = Entity.class.getDeclaredField("id");
                        id.setAccessible(true);
                        id.setInt(player, players.size() + 1);
                        players.put(integer(op, k, 1), player);
                    }
                    manager.addPlayer(SectionPos.of(integer(op, k, 2), 0, integer(op, k, 3)), player);
                }
                case "unplayer" -> {
                    expect(op, k, 3);
                    ServerPlayer player = players.get(integer(op, k, 1));
                    if (player == null) {
                        throw new CaseError("operation " + k + ": no player " + integer(op, k, 1));
                    }
                    manager.removePlayer(SectionPos.of(integer(op, k, 2), 0, integer(op, k, 3)), player);
                }
                case "view" -> {
                    expect(op, k, 1);
                    manager.view(integer(op, k, 1));
                }
                case "simulation" -> {
                    expect(op, k, 1);
                    manager.updateSimulationDistance(integer(op, k, 1));
                }
                case "ticket" -> {
                    expect(op, k, 4);
                    out.writeBoolean(storage.addTicket(chunk(op, k, 3), new Ticket(type(op, k, 1), integer(op, k, 2))));
                }
                case "unticket" -> {
                    expect(op, k, 4);
                    out.writeBoolean(storage.removeTicket(chunk(op, k, 3), new Ticket(type(op, k, 1), integer(op, k, 2))));
                }
                case "update" -> {
                    expect(op, k, 0);
                    out.writeBoolean(manager.runAllUpdates(map));
                }
                case "promote" -> {
                    expect(op, k, 0);
                    out.writeBoolean(manager.modified);
                    manager.modified = false;
                }
                case "dispatch" -> {
                    expect(op, k, 1);
                    out.writeInt(drain(worker, integer(op, k, 1)));
                }
                case "main" -> {
                    expect(op, k, 1);
                    out.writeInt(drain(main, integer(op, k, 1)));
                }
                case "ready" -> {
                    expect(op, k, 2);
                    long pos = chunk(op, k, 1);
                    ChunkHolder holder = manager.updating.get(pos);
                    if (holder == null) {
                        holder = manager.pending.get(pos);
                    }
                    out.writeBoolean(holder != null && ((Holder) holder).ready());
                }
                case "ready_first" -> {
                    expect(op, k, 1);
                    int most = integer(op, k, 1);
                    int readied = 0;
                    for (ChunkHolder holder : manager.updating.values()) {
                        if (readied >= most) {
                            break;
                        }
                        if (((Holder) holder).ready()) {
                            readied++;
                        }
                    }
                    out.writeInt(readied);
                }
                case "drop" -> {
                    expect(op, k, 0);
                    List<Long> moved = manager.drop();
                    out.writeInt(moved.size());
                    for (long pos : moved) {
                        out.writeLong(pos);
                    }
                }
                case "unload" -> {
                    expect(op, k, 1);
                    out.writeInt(drain(manager.unloads, integer(op, k, 1)));
                }
                case "nearby" -> {
                    expect(op, k, 2);
                    TriState nearby = manager.hasPlayersNearby(chunk(op, k, 1));
                    out.writeByte(nearby == TriState.TRUE ? 0 : nearby == TriState.DEFAULT ? 1 : 2);
                }
                case "spawn_count" -> {
                    expect(op, k, 0);
                    out.writeInt(manager.getNaturalSpawnChunkCount());
                }
                case "brief" -> {
                    expect(op, k, 0);
                    dump(out, manager, storage, false);
                }
                case "dump" -> {
                    expect(op, k, 0);
                    dump(out, manager, storage, true);
                }
                default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
            }
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    // Runs up to `count` of the queue's tasks, each as it comes, and how many ran.
    private static int drain(Queue<Runnable> queue, int count) {
        int ran = 0;
        while (ran < count) {
            Runnable task = queue.poll();
            if (task == null) {
                break;
            }
            task.run();
            ran++;
        }
        return ran;
    }

    /** The manager, with {@code ChunkMap}'s holders. */
    private static final class Manager extends DistanceManager {
        final Long2ObjectLinkedOpenHashMap<ChunkHolder> updating = new Long2ObjectLinkedOpenHashMap<>();
        final Long2ObjectLinkedOpenHashMap<ChunkHolder> pending = new Long2ObjectLinkedOpenHashMap<>();
        final LongSet toDrop = new LongOpenHashSet();
        final ArrayDeque<Runnable> unloads = new ArrayDeque<>();
        boolean modified;

        Manager(TicketStorage storage, Executor worker, Executor main) {
            super(storage, worker, main);
        }

        void view(int viewDistance) {
            this.updatePlayerTickets(viewDistance);
        }

        @Override
        protected boolean isChunkToRemove(long node) {
            return this.toDrop.contains(node);
        }

        @Override
        protected ChunkHolder getChunk(long node) {
            return this.updating.get(node);
        }

        // ChunkMap.updateChunkScheduling.
        @Override
        protected ChunkHolder updateChunkScheduling(long node, int level, ChunkHolder chunk, int oldLevel) {
            if (!ChunkLevel.isLoaded(oldLevel) && !ChunkLevel.isLoaded(level)) {
                return chunk;
            }
            if (chunk != null) {
                chunk.setTicketLevel(level);
            }
            if (chunk != null) {
                if (!ChunkLevel.isLoaded(level)) {
                    this.toDrop.add(node);
                } else {
                    this.toDrop.remove(node);
                }
            }
            if (ChunkLevel.isLoaded(level) && chunk == null) {
                chunk = this.pending.remove(node);
                if (chunk != null) {
                    chunk.setTicketLevel(level);
                } else {
                    chunk = new Holder(node, level);
                }
                this.updating.put(node, chunk);
                this.modified = true;
            }
            return chunk;
        }

        // The start of ChunkMap.processUnloads, and scheduleUnload with the holder's saves done.
        List<Long> drop() {
            List<Long> moved = new java.util.ArrayList<>();
            for (LongIterator iterator = this.toDrop.iterator(); iterator.hasNext(); iterator.remove()) {
                long pos = iterator.nextLong();
                ChunkHolder holder = this.updating.get(pos);
                if (holder != null) {
                    this.updating.remove(pos);
                    this.pending.put(pos, holder);
                    this.modified = true;
                    moved.add(pos);
                    this.unloads.add(() -> this.pending.remove(pos, holder));
                }
            }
            return moved;
        }
    }

    /** Vanilla's holder, with its futures cut down to the chunk ticking its entities. */
    private static final class Holder extends ChunkHolder {
        static final LevelHeightAccessor HEIGHT = LevelHeightAccessor.create(0, 16);
        static final CompletableFuture<ChunkResult<LevelChunk>> UNLOADED = CompletableFuture.completedFuture(ChunkHolder.UNLOADED_LEVEL_CHUNK);
        int oldLevel = ChunkLevel.MAX_LEVEL + 1;
        CompletableFuture<ChunkResult<LevelChunk>> ticking = UNLOADED;

        Holder(long node, int level) {
            super(ChunkPos.unpack(node), level, HEIGHT, null, (pos, old, now, set) -> {}, null);
        }

        @Override
        protected void updateHighestAllowedStatus(ChunkMap scheduler) {
        }

        // ChunkHolder.updateFutures, as far as the entity-ticking future goes.
        @Override
        protected void updateFutures(ChunkMap scheduler, Executor mainThreadExecutor) {
            boolean was = ChunkLevel.fullStatus(this.oldLevel).isOrAfter(FullChunkStatus.ENTITY_TICKING);
            boolean is = ChunkLevel.fullStatus(this.getTicketLevel()).isOrAfter(FullChunkStatus.ENTITY_TICKING);
            if (!was && is) {
                if (this.ticking != UNLOADED) {
                    throw new IllegalStateException();
                }
                this.ticking = new CompletableFuture<>();
            }
            if (was && !is) {
                this.ticking.complete(ChunkHolder.UNLOADED_LEVEL_CHUNK);
                this.ticking = UNLOADED;
            }
            this.oldLevel = this.getTicketLevel();
        }

        @Override
        public CompletableFuture<ChunkResult<LevelChunk>> getEntityTickingChunkFuture() {
            return this.ticking;
        }

        // The chunk ticks its entities: whether it was waited for.
        boolean ready() {
            if (this.ticking == UNLOADED || this.ticking.isDone()) {
                return false;
            }
            this.ticking.complete(ChunkHolder.UNLOADED_LEVEL_CHUNK);
            return true;
        }

        int state() {
            return this.ticking == UNLOADED ? 0 : this.ticking.isDone() ? 2 : 1;
        }
    }

    // What the manager, its dispatcher and the holders keep, each table in its order, and if
    // `full`, the trackers' levels too.
    private static void dump(DataOutputStream out, Manager manager, TicketStorage storage, boolean full) throws Exception {
        holders(out, manager.updating);
        holders(out, manager.pending);
        out.writeInt(manager.toDrop.size());
        for (LongIterator it = manager.toDrop.iterator(); it.hasNext(); ) {
            out.writeLong(it.nextLong());
        }
        out.writeInt(manager.unloads.size());
        out.writeBoolean(manager.modified);
        longs(out, (LongSet) get(DistanceManager.class, manager, "ticketsToRelease"));
        Object dispatcher = get(DistanceManager.class, manager, "ticketDispatcher");
        Class<?> throttling = dispatcher.getClass();
        Class<?> base = throttling.getSuperclass();
        out.writeBoolean((Boolean) get(base, dispatcher, "sleeping"));
        longs(out, (LongSet) get(throttling, dispatcher, "chunkPositionsInExecution"));
        Object queue = get(base, dispatcher, "queue");
        out.writeInt((Integer) get(queue.getClass(), queue, "topPriorityQueueIndex"));
        @SuppressWarnings("unchecked")
        List<Long2ObjectLinkedOpenHashMap<List<Runnable>>> levels = (List<Long2ObjectLinkedOpenHashMap<List<Runnable>>>) get(queue.getClass(), queue, "queuesPerPriority");
        for (int level = 0; level < levels.size(); level++) {
            Long2ObjectLinkedOpenHashMap<List<Runnable>> at = levels.get(level);
            if (at.isEmpty()) {
                continue;
            }
            out.writeInt(level);
            out.writeInt(at.size());
            for (ObjectIterator<Long2ObjectMap.Entry<List<Runnable>>> it = at.long2ObjectEntrySet().fastIterator(); it.hasNext(); ) {
                Long2ObjectMap.Entry<List<Runnable>> e = it.next();
                out.writeLong(e.getLongKey());
                out.writeInt(e.getValue().size());
            }
        }
        out.writeInt(-1);
        Object executor = get(base, dispatcher, "dispatcher");
        Object strict = get(executor.getClass().getSuperclass(), executor, "queue");
        Queue<?>[] priorities = (Queue<?>[]) get(strict.getClass(), strict, "queues");
        for (Queue<?> q : priorities) {
            out.writeInt(q.size());
        }
        @SuppressWarnings("unchecked")
        Long2ObjectOpenHashMap<List<Ticket>> tickets = (Long2ObjectOpenHashMap<List<Ticket>>) get(TicketStorage.class, storage, "tickets");
        out.writeInt(tickets.size());
        Field left = Ticket.class.getDeclaredField("ticksLeft");
        left.setAccessible(true);
        for (ObjectIterator<Long2ObjectMap.Entry<List<Ticket>>> it = tickets.long2ObjectEntrySet().fastIterator(); it.hasNext(); ) {
            Long2ObjectMap.Entry<List<Ticket>> e = it.next();
            out.writeLong(e.getLongKey());
            out.writeInt(e.getValue().size());
            for (Ticket t : e.getValue()) {
                out.writeByte(BuiltInRegistries.TICKET_TYPE.getId(t.getType()));
                out.writeInt(t.getTicketLevel());
                out.writeLong(left.getLong(t));
            }
        }
        text(out, manager.getDebugStatus());
        if (!full) {
            return;
        }
        Object simulation = get(DistanceManager.class, manager, "simulationChunkTracker");
        bytes(out, (Long2ByteMap) get(simulation.getClass(), simulation, "chunks"));
        Object spawn = get(DistanceManager.class, manager, "naturalSpawnChunkCounter");
        Class<?> fixed = spawn.getClass();
        bytes(out, (Long2ByteMap) get(fixed, spawn, "chunks"));
        Object player = get(DistanceManager.class, manager, "playerTicketManager");
        bytes(out, (Long2ByteMap) get(fixed, player, "chunks"));
        Long2IntMap queueLevels = (Long2IntMap) get(player.getClass(), player, "queueLevels");
        out.writeInt(queueLevels.size());
        for (ObjectIterator<Long2IntMap.Entry> it = queueLevels.long2IntEntrySet().iterator(); it.hasNext(); ) {
            Long2IntMap.Entry e = it.next();
            out.writeLong(e.getLongKey());
            out.writeInt(e.getIntValue());
        }
        out.writeInt((Integer) get(player.getClass(), player, "viewDistance"));
        out.writeInt((Integer) get(DistanceManager.class, manager, "simulationDistance"));
    }

    private static void holders(DataOutputStream out, Long2ObjectLinkedOpenHashMap<ChunkHolder> holders) throws IOException {
        out.writeInt(holders.size());
        for (ObjectIterator<Long2ObjectMap.Entry<ChunkHolder>> it = holders.long2ObjectEntrySet().fastIterator(); it.hasNext(); ) {
            Long2ObjectMap.Entry<ChunkHolder> e = it.next();
            Holder holder = (Holder) e.getValue();
            out.writeLong(e.getLongKey());
            out.writeInt(holder.getTicketLevel());
            out.writeByte(holder.state());
            out.writeInt(holder.ticking.getNumberOfDependents());
        }
    }

    private static void bytes(DataOutputStream out, Long2ByteMap map) throws IOException {
        out.writeInt(map.size());
        for (ObjectIterator<Long2ByteMap.Entry> it = map.long2ByteEntrySet().iterator(); it.hasNext(); ) {
            Long2ByteMap.Entry e = it.next();
            out.writeLong(e.getLongKey());
            out.writeInt(e.getByteValue());
        }
    }

    private static void longs(DataOutputStream out, LongSet set) throws IOException {
        out.writeInt(set.size());
        for (LongIterator it = set.iterator(); it.hasNext(); ) {
            out.writeLong(it.nextLong());
        }
    }

    private static Object get(Class<?> owner, Object of, String field) throws Exception {
        Field f = owner.getDeclaredField(field);
        f.setAccessible(true);
        return f.get(of);
    }

    private static Object allocate(Class<?> type) throws Exception {
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field theUnsafe = unsafeClass.getDeclaredField("theUnsafe");
        theUnsafe.setAccessible(true);
        Method allocate = unsafeClass.getMethod("allocateInstance", Class.class);
        return allocate.invoke(theUnsafe.get(null), type);
    }

    private static void text(DataOutputStream out, String text) throws IOException {
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(bytes.length);
        out.write(bytes);
    }

    private static void expect(JsonArray op, int k, int args) {
        if (op.size() != args + 1) {
            throw new CaseError("operation " + k + " takes " + args + " arguments");
        }
    }

    private static int integer(JsonArray op, int k, int i) {
        return Args.asInt(op.get(i), "operation " + k + "'s argument " + i);
    }

    // Arguments `i` and `i + 1`, a chunk's `x` and `z`, packed.
    private static long chunk(JsonArray op, int k, int i) {
        return ChunkPos.pack(integer(op, k, i), integer(op, k, i + 1));
    }

    private static TicketType type(JsonArray op, int k, int i) {
        String name = Args.asString(op.get(i), "operation " + k + "'s ticket type");
        if (!BuiltInRegistries.TICKET_TYPE.containsKey(Identifier.withDefaultNamespace(name))) {
            throw new CaseError("operation " + k + ": no ticket type `" + name + "`");
        }
        return BuiltInRegistries.TICKET_TYPE.getValue(Identifier.withDefaultNamespace(name));
    }

    static {
        // The levels the cases are written for.
        if (ChunkLevel.MAX_LEVEL != 44) {
            throw new IllegalStateException("ChunkLevel.MAX_LEVEL is " + ChunkLevel.MAX_LEVEL + ", not 44");
        }
    }
}
