package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import it.unimi.dsi.fastutil.longs.Long2IntMap;
import it.unimi.dsi.fastutil.longs.Long2IntOpenHashMap;
import it.unimi.dsi.fastutil.objects.ObjectIterator;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.List;
import net.minecraft.server.level.ChunkTracker;
import net.minecraft.world.level.ChunkPos;

/**
 * `levels`: vanilla's own {@link ChunkTracker}, the graph every chunk tracker is, through a list
 * of operations, with each level it sets written as it's set.
 *
 * <p>Its levels and sources are kept in maps, as the simulation and player trackers keep theirs:
 * the case says how many levels there are, the level of a chunk with none, the level from which
 * a set level is taken out of the map, and the source level of a chunk with no source.
 */
final class LevelsProbe implements Probe {
    @Override
    public String name() {
        return "levels";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`levels` takes no blobs");
        }
        JsonArray ops = Args.array(input, "ops");
        int count = Args.asInt(Args.field(input, "level_count"), "`level_count`");
        if (count < 2 || count > 253) {
            throw new CaseError("`level_count` must be from 2 to 253");
        }
        int unset = Args.asInt(Args.field(input, "unset"), "`unset`");
        int keepBelow = Args.asInt(Args.field(input, "keep_below"), "`keep_below`");
        int noSource = Args.asInt(Args.field(input, "no_source"), "`no_source`");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        Tracker tracker = new Tracker(count, unset, keepBelow, noSource, out);
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            JsonArray op = ops.get(k).getAsJsonArray();
            String name = Args.asString(op.get(0), "operation " + k + "'s name");
            // Each operation's levels set come first, as they're set, then a 0 and its result.
            ByteArrayOutputStream result = new ByteArrayOutputStream();
            DataOutputStream after = new DataOutputStream(result);
            switch (name) {
                case "source" -> {
                    expect(op, k, 3);
                    tracker.sources.put(chunk(op, k), integer(op, k, 3));
                }
                case "unsource" -> {
                    expect(op, k, 2);
                    tracker.sources.remove(chunk(op, k));
                }
                case "update" -> {
                    expect(op, k, 4);
                    long chunk = chunk(op, k);
                    int level = integer(op, k, 3);
                    JsonElement v = op.get(4);
                    if (!v.isJsonPrimitive() || !v.getAsJsonPrimitive().isBoolean()) {
                        throw new CaseError("operation " + k + "'s argument 4 must be a boolean");
                    }
                    tracker.update(chunk, level, v.getAsBoolean());
                }
                case "set" -> {
                    expect(op, k, 3);
                    tracker.keep(chunk(op, k), integer(op, k, 3));
                }
                case "run" -> {
                    expect(op, k, 1);
                    after.writeInt(tracker.run(integer(op, k, 1)));
                }
                case "dump" -> {
                    expect(op, k, 0);
                    after.writeBoolean(tracker.working());
                    after.writeInt(tracker.getQueueSize());
                    after.writeInt(tracker.levels.size());
                    ObjectIterator<Long2IntMap.Entry> it = tracker.levels.long2IntEntrySet().iterator();
                    while (it.hasNext()) {
                        Long2IntMap.Entry e = it.next();
                        after.writeLong(e.getLongKey());
                        after.writeInt(e.getIntValue());
                    }
                }
                default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
            }
            out.writeByte(0);
            out.write(result.toByteArray());
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    /** The graph with its levels and sources in maps, writing each level set as a 1, the chunk and the level. */
    private static final class Tracker extends ChunkTracker {
        final Long2IntOpenHashMap levels = new Long2IntOpenHashMap();
        final Long2IntOpenHashMap sources = new Long2IntOpenHashMap();
        private final int keepBelow;
        private final DataOutputStream out;

        Tracker(int count, int unset, int keepBelow, int noSource, DataOutputStream out) {
            super(count, 16, 256);
            this.levels.defaultReturnValue(unset);
            this.sources.defaultReturnValue(noSource);
            this.keepBelow = keepBelow;
            this.out = out;
        }

        void keep(long node, int level) {
            if (level >= this.keepBelow) {
                this.levels.remove(node);
            } else {
                this.levels.put(node, level);
            }
        }

        int run(int count) {
            return this.runUpdates(count);
        }

        boolean working() {
            return this.hasWork();
        }

        @Override
        protected int getLevelFromSource(long to) {
            return this.sources.get(to);
        }

        @Override
        protected int getLevel(long node) {
            return this.levels.get(node);
        }

        @Override
        protected void setLevel(long node, int level) {
            try {
                this.out.writeByte(1);
                this.out.writeLong(node);
                this.out.writeInt(level);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
            this.keep(node, level);
        }
    }

    private static void expect(JsonArray op, int k, int args) {
        if (op.size() != args + 1) {
            throw new CaseError("operation " + k + " takes " + args + " arguments");
        }
    }

    private static int integer(JsonArray op, int k, int i) {
        return Args.asInt(op.get(i), "operation " + k + "'s argument " + i);
    }

    private static long chunk(JsonArray op, int k) {
        return ChunkPos.pack(integer(op, k, 1), integer(op, k, 2));
    }
}
