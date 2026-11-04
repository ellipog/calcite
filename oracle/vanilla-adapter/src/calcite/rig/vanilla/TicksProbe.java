package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import it.unimi.dsi.fastutil.longs.Long2LongMap;
import it.unimi.dsi.fastutil.longs.Long2LongOpenHashMap;
import it.unimi.dsi.fastutil.longs.LongOpenHashSet;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.ticks.LevelChunkTicks;
import net.minecraft.world.ticks.LevelTicks;
import net.minecraft.world.ticks.SavedTick;
import net.minecraft.world.ticks.ScheduledTick;
import net.minecraft.world.ticks.TickPriority;

/**
 * `ticks`: a level's scheduled ticks, in vanilla's own {@link LevelTicks} and
 * {@link LevelChunkTicks}, through a list of operations, with the ticks each `tick` runs in the
 * order it runs them.
 *
 * <p>What's ticked is a number, 0 to 127, each the boxed {@code Integer} Java keeps for it, so
 * two ticks of the same number are of the same thing, as two of a block are. The level's
 * `tickCheck` says a chunk ticks if the last `tick` gave it.
 */
final class TicksProbe implements Probe {
    @Override
    public String name() {
        return "ticks";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`ticks` takes no blobs");
        }
        JsonArray ops = Args.array(input, "ops");
        LongOpenHashSet ticking = new LongOpenHashSet();
        LevelTicks<Integer> level = new LevelTicks<>(ticking::contains);
        // Each chunk's containers, in the order they were added, as the level doesn't give them.
        Map<Long, LevelChunkTicks<Integer>> chunks = new LinkedHashMap<>();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            JsonArray op = ops.get(k).getAsJsonArray();
            String name = Args.asString(op.get(0), "operation " + k + "'s name");
            switch (name) {
                case "add" -> {
                    expect(op, k, 3);
                    ChunkPos pos = new ChunkPos(integer(op, k, 1), integer(op, k, 2));
                    LevelChunkTicks<Integer> container;
                    if (op.get(3).isJsonNull()) {
                        container = new LevelChunkTicks<>();
                    } else {
                        container = new LevelChunkTicks<>(saved(op, k));
                    }
                    chunks.remove(pos.pack());
                    chunks.put(pos.pack(), container);
                    level.addContainer(pos, container);
                }
                case "remove" -> {
                    expect(op, k, 2);
                    ChunkPos pos = new ChunkPos(integer(op, k, 1), integer(op, k, 2));
                    chunks.remove(pos.pack());
                    level.removeContainer(pos);
                }
                case "schedule" -> {
                    expect(op, k, 7);
                    level.schedule(new ScheduledTick<>(kind(op, k, 1), pos(op, k, 2), int64(op, k, 5), priority(op, k, 6), int64(op, k, 7)));
                }
                case "unpack" -> {
                    expect(op, k, 3);
                    LevelChunkTicks<Integer> container = container(chunks, op, k);
                    container.unpack(int64(op, k, 3));
                }
                case "pack" -> {
                    expect(op, k, 3);
                    List<SavedTick<Integer>> saved = container(chunks, op, k).pack(int64(op, k, 3));
                    out.writeInt(saved.size());
                    for (SavedTick<Integer> t : saved) {
                        out.writeInt(t.type());
                        out.writeInt(t.pos().getX());
                        out.writeInt(t.pos().getY());
                        out.writeInt(t.pos().getZ());
                        out.writeInt(t.delay());
                        out.writeInt(t.priority().getValue());
                    }
                }
                case "has" -> {
                    expect(op, k, 4);
                    out.writeBoolean(level.hasScheduledTick(pos(op, k, 2), kind(op, k, 1)));
                }
                case "count" -> {
                    expect(op, k, 0);
                    out.writeInt(level.count());
                }
                case "tick" -> {
                    expect(op, k, 3);
                    long time = int64(op, k, 1);
                    int max = integer(op, k, 2);
                    ticking.clear();
                    if (!op.get(3).isJsonArray()) {
                        throw new CaseError("operation " + k + "'s ticking chunks must be an array");
                    }
                    for (JsonElement c : op.get(3).getAsJsonArray()) {
                        JsonArray xz = c.getAsJsonArray();
                        ticking.add(ChunkPos.pack(xz.get(0).getAsInt(), xz.get(1).getAsInt()));
                    }
                    List<long[]> ran = new ArrayList<>();
                    level.tick(time, max, (pos, type) -> ran.add(new long[] {type, pos.getX(), pos.getY(), pos.getZ()}));
                    out.writeInt(ran.size());
                    for (long[] r : ran) {
                        for (long v : r) {
                            out.writeInt((int) v);
                        }
                    }
                }
                case "dump" -> {
                    expect(op, k, 0);
                    dump(level, chunks, out);
                }
                default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
            }
        }
        out.flush();
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    // `nextTickForContainer` in its table's order, an `int` count and each chunk and time as
    // `long`s; then each container, in the order the chunks were added, as its chunk, a `long`,
    // its scheduled ticks in its queue's order, an `int` count and each tick, and `count`.
    private static void dump(LevelTicks<Integer> level, Map<Long, LevelChunkTicks<Integer>> chunks, DataOutputStream out) throws Exception {
        Field field = LevelTicks.class.getDeclaredField("nextTickForContainer");
        field.setAccessible(true);
        Long2LongOpenHashMap next = (Long2LongOpenHashMap) field.get(level);
        out.writeInt(next.size());
        for (Long2LongMap.Entry e : next.long2LongEntrySet()) {
            out.writeLong(e.getLongKey());
            out.writeLong(e.getLongValue());
        }
        out.writeInt(chunks.size());
        for (Map.Entry<Long, LevelChunkTicks<Integer>> e : chunks.entrySet()) {
            out.writeLong(e.getKey());
            List<ScheduledTick<Integer>> queue = e.getValue().getAll().toList();
            out.writeInt(queue.size());
            for (ScheduledTick<Integer> t : queue) {
                out.writeInt(t.type());
                out.writeInt(t.pos().getX());
                out.writeInt(t.pos().getY());
                out.writeInt(t.pos().getZ());
                out.writeLong(t.triggerTick());
                out.writeInt(t.priority().getValue());
                out.writeLong(t.subTickOrder());
            }
            out.writeInt(e.getValue().count());
        }
    }

    // The saved ticks of `add` operation `k`, each `[kind, x, y, z, delay, priority]`.
    private static List<SavedTick<Integer>> saved(JsonArray op, int k) {
        if (!op.get(3).isJsonArray()) {
            throw new CaseError("operation " + k + "'s saved ticks must be an array or null");
        }
        List<SavedTick<Integer>> out = new ArrayList<>();
        for (JsonElement e : op.get(3).getAsJsonArray()) {
            JsonArray t = e.getAsJsonArray();
            if (t.size() != 6) {
                throw new CaseError("operation " + k + "'s saved ticks each take 6 numbers");
            }
            int kind = t.get(0).getAsInt();
            if (kind < 0 || kind > 127) {
                throw new CaseError("operation " + k + ": a kind is 0 to 127");
            }
            out.add(new SavedTick<>(Integer.valueOf(kind), new BlockPos(t.get(1).getAsInt(), t.get(2).getAsInt(), t.get(3).getAsInt()), t.get(4).getAsInt(), TickPriority.byValue(t.get(5).getAsInt())));
        }
        return out;
    }

    private static LevelChunkTicks<Integer> container(Map<Long, LevelChunkTicks<Integer>> chunks, JsonArray op, int k) {
        LevelChunkTicks<Integer> container = chunks.get(ChunkPos.pack(integer(op, k, 1), integer(op, k, 2)));
        if (container == null) {
            throw new CaseError("operation " + k + ": that chunk has no ticks");
        }
        return container;
    }

    private static void expect(JsonArray op, int k, int args) {
        if (op.size() != args + 1) {
            throw new CaseError("operation " + k + " takes " + args + " arguments");
        }
    }

    private static int integer(JsonArray op, int k, int i) {
        return Args.asInt(op.get(i), "operation " + k + "'s argument " + i);
    }

    // A `long`, given as its decimal string.
    private static long int64(JsonArray op, int k, int i) {
        return Args.parseLong(Args.asString(op.get(i), "operation " + k + "'s argument " + i), "operation " + k + "'s argument " + i);
    }

    private static Integer kind(JsonArray op, int k, int i) {
        int kind = integer(op, k, i);
        if (kind < 0 || kind > 127) {
            throw new CaseError("operation " + k + ": a kind is 0 to 127");
        }
        return Integer.valueOf(kind);
    }

    private static BlockPos pos(JsonArray op, int k, int i) {
        return new BlockPos(integer(op, k, i), integer(op, k, i + 1), integer(op, k, i + 2));
    }

    private static TickPriority priority(JsonArray op, int k, int i) {
        return TickPriority.byValue(integer(op, k, i));
    }
}
