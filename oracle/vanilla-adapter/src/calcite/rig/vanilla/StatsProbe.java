package calcite.rig.vanilla;

import com.google.common.collect.Sets;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import it.unimi.dsi.fastutil.objects.Object2IntMap;
import it.unimi.dsi.fastutil.objects.Object2IntOpenHashMap;
import java.io.File;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Stream;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.stats.ServerStatsCounter;
import net.minecraft.stats.Stat;
import net.minecraft.stats.StatType;
import net.minecraft.util.StrictJsonParser;
import net.minecraft.util.datafix.DataFixers;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `stats`: a player's statistics as {@link ServerStatsCounter} keeps them (CAL-164). The case's
 * `json`, where it has one, is what the player's file held, read by `parse` as a server reads it
 * as the player joins, through `STATS_CODEC`, with what it logs; then its `ops` run in turn:
 * `["award", type, value, by]` increments a stat, `["mark_all_dirty"]` marks every stat to be
 * sent, `["send"]` gives what `sendStats` would send, in the order its packet writes them, and
 * `["save"]` the file `save` writes, its stat types put in their registry's order: vanilla groups
 * them in a `HashMap` keyed by identity, in another order each run, so only the order of each
 * type's stats is kept as it wrote them. A file whose `DataVersion` is older than 26.3's is
 * upgraded by the data fixers first, which Calcite doesn't do, so the cases give 26.3's.
 */
final class StatsProbe implements Probe {
    @Override
    public String name() {
        return "stats";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        // Built before anything is logged, since building it logs.
        DataFixers.getDataFixer();
        Path folder = Files.createTempDirectory("calcite-stats");
        Path file = folder.resolve("players").resolve("stats").resolve("player.json");
        Lines lines = new Lines(folder.toString() + File.separator);
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        try {
            // The file isn't there yet, so the constructor reads nothing and needs no server.
            ServerStatsCounter counter = new ServerStatsCounter(null, file);
            JsonObject output = new JsonObject();
            if (input.has("json")) {
                JsonElement element;
                try {
                    element = StrictJsonParser.parse(Args.string(input, "json"));
                } catch (JsonParseException e) {
                    throw new CaseError("`json` isn't JSON: " + e.getMessage());
                }
                counter.parse(DataFixers.getDataFixer(), element);
            }
            output.add("lines", lines.take());
            JsonArray results = new JsonArray();
            JsonArray ops = input.has("ops") ? Args.array(input, "ops") : new JsonArray();
            for (int k = 0; k < ops.size(); k++) {
                if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                    throw new CaseError("operation " + k + " isn't a list with its name first");
                }
                JsonArray op = ops.get(k).getAsJsonArray();
                String name = Args.asString(op.get(0), "operation " + k);
                switch (name) {
                    case "award" -> {
                        if (op.size() != 4) {
                            throw new CaseError("operation " + k + ": `award` takes a type, a value and a count");
                        }
                        Stat<?> stat = stat(Args.asString(op.get(1), "operation " + k + "'s type"), Args.asString(op.get(2), "operation " + k + "'s value"), k);
                        counter.increment(null, stat, Args.asInt(op.get(3), "operation " + k + "'s count"));
                    }
                    case "mark_all_dirty" -> counter.markAllDirty();
                    case "send" -> results.add(sent(counter));
                    case "save" -> {
                        counter.save();
                        JsonObject saved = new JsonObject();
                        saved.addProperty("saved", typesInOrder(Files.readString(file, StandardCharsets.UTF_8)));
                        saved.add("lines", lines.take());
                        results.add(saved);
                    }
                    default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
                }
            }
            output.add("results", results);
            return Result.ok(output);
        } finally {
            root.removeAppender(lines);
            lines.stop();
            try (Stream<Path> walk = Files.walk(folder)) {
                for (Path p : walk.sorted(Comparator.reverseOrder()).toList()) {
                    Files.deleteIfExists(p);
                }
            }
        }
    }

    // The saved file `text` with its `stats`' types in `STAT_TYPE`'s order, written again as `save`
    // writes it, pretty.
    private static String typesInOrder(String text) {
        JsonObject root = StrictJsonParser.parse(text).getAsJsonObject();
        JsonObject stats = root.getAsJsonObject("stats");
        JsonObject ordered = new JsonObject();
        for (StatType<?> type : BuiltInRegistries.STAT_TYPE) {
            String key = BuiltInRegistries.STAT_TYPE.getKey(type).toString();
            if (stats.has(key)) {
                ordered.add(key, stats.get(key));
            }
        }
        JsonObject out = new JsonObject();
        for (var e : root.entrySet()) {
            out.add(e.getKey(), e.getKey().equals("stats") ? ordered : e.getValue());
        }
        return new GsonBuilder().setPrettyPrinting().create().toJson(out);
    }

    // The stat of the type and value named, both whole IDs in their registries.
    private static Stat<?> stat(String type, String value, int k) {
        StatType<?> statType = BuiltInRegistries.STAT_TYPE.getValue(Identifier.parse(type));
        if (statType == null) {
            throw new CaseError("operation " + k + ": no stat type `" + type + "`");
        }
        return of(statType, value, k);
    }

    private static <T> Stat<T> of(StatType<T> type, String value, int k) {
        Registry<T> registry = type.getRegistry();
        Identifier id = Identifier.parse(value);
        if (!registry.containsKey(id)) {
            throw new CaseError("operation " + k + ": `" + value + "` isn't in the type's registry");
        }
        return type.get(registry.getValue(id));
    }

    // What `sendStats` sends: the marked stats, copied with `Sets.newHashSet` and no longer marked,
    // each with its count in an `Object2IntOpenHashMap`, which the packet writes in its order.
    @SuppressWarnings("unchecked")
    private static JsonObject sent(ServerStatsCounter counter) throws Exception {
        Field field = ServerStatsCounter.class.getDeclaredField("dirty");
        field.setAccessible(true);
        Set<Stat<?>> dirty = (Set<Stat<?>>) field.get(counter);
        Set<Stat<?>> result = Sets.newHashSet(dirty);
        dirty.clear();
        Object2IntMap<Stat<?>> statsToSend = new Object2IntOpenHashMap<>();
        for (Stat<?> stat : result) {
            statsToSend.put(stat, counter.getValue(stat));
        }
        JsonArray out = new JsonArray();
        for (Object2IntMap.Entry<Stat<?>> e : statsToSend.object2IntEntrySet()) {
            out.add(entry(e.getKey(), e.getIntValue()));
        }
        JsonObject sent = new JsonObject();
        sent.add("sent", out);
        return sent;
    }

    private static <T> JsonArray entry(Stat<T> stat, int count) {
        JsonArray a = new JsonArray();
        a.add(BuiltInRegistries.STAT_TYPE.getKey(stat.getType()).toString());
        a.add(stat.getType().getRegistry().getKey(stat.getValue()).toString());
        a.add(count);
        return a;
    }

    // What vanilla logged, each line its level and its message, the probe's folder taken out.
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();
        final String folder;

        Lines(String folder) {
            super("stats-probe", null, null, true, Property.EMPTY_ARRAY);
            this.folder = folder;
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }

        JsonArray take() {
            JsonArray out = new JsonArray();
            for (LogEvent event : taken) {
                out.add(event.getLevel().name() + " " + event.getMessage().getFormattedMessage().replace(folder, "").replace(File.separatorChar, '/'));
            }
            taken.clear();
            return out;
        }
    }
}
