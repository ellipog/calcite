package calcite.rig.vanilla;

import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.TreeSet;
import java.util.stream.Stream;
import net.minecraft.SharedConstants;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.chunk.storage.RegionFile;
import net.minecraft.world.level.chunk.storage.RegionStorageInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * The round trip's check (G5.2, `rig/runner/roundtrip.py`): a world vanilla saved, and the same
 * world after Calcite loaded and saved it, read file by file with vanilla's own readers.
 *
 * <pre>java calcite.rig.vanilla.WorldCheck EXPECTED ACTUAL</pre>
 *
 * <p>Each region file is opened with {@link RegionFile} and every chunk read with
 * {@link NbtIo#read}; each `.dat` with {@link NbtIo#readCompressed}; each `.json` with Gson's
 * {@link JsonParser}; anything else as bytes. Two tags are the same if they're
 * {@link Tag#equals}, which a compound is whatever order its keys are in; the bytes
 * {@link NbtIo#write} gives each are compared too, and a difference in order alone is counted
 * but isn't one. A world's `LastPlayed` is when it was saved, so it's left out, and so are the
 * region files' timestamps, which are when each chunk was; a file's backup, `level.dat_old`
 * or a player's `.dat_old`, holds the file it replaced, so ACTUAL's is compared with EXPECTED's
 * file. Anything vanilla logs reading ACTUAL is a difference.
 *
 * <p>It prints each difference, then a line of counts, and exits with 1 if there was one.
 */
final class WorldCheck {
    // The most of a value shown in a difference.
    private static final int SHOWN = 160;
    // The most differences shown for a file.
    private static final int PER_FILE = 5;

    // Made after the bootstrap, which `Level` needs.
    private final RegionStorageInfo info = new RegionStorageInfo("check", Level.OVERWORLD, "chunk");
    private final List<String> differences = new ArrayList<>();
    private int files;
    private int chunks;
    private int reordered;

    public static void main(String[] args) throws IOException {
        if (args.length != 2) {
            System.err.println("usage: WorldCheck EXPECTED ACTUAL");
            System.exit(2);
        }
        // The bootstrap sends `System.out` through the log, which marks each line.
        PrintStream out = System.out;
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        Path expected = Path.of(args[0]);
        Path actual = Path.of(args[1]);
        Lines lines = new Lines();
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        WorldCheck check = new WorldCheck();
        try {
            check.compare(expected, actual, lines);
        } finally {
            root.removeAppender(lines);
        }
        for (String d : check.differences) {
            out.println(d);
        }
        out.println("checked " + check.files + " files and " + check.chunks + " chunks: "
            + check.differences.size() + " differences, " + check.reordered + " in order alone");
        out.flush();
        System.exit(check.differences.isEmpty() ? 0 : 1);
    }

    private void compare(Path expected, Path actual, Lines lines) throws IOException {
        TreeSet<String> names = new TreeSet<>(files(expected));
        TreeSet<String> given = new TreeSet<>(files(actual));
        for (String name : given) {
            if (!names.contains(name) && !(isBackup(name) && names.contains(original(name)))) {
                differences.add(name + ": only in Calcite's save");
            }
        }
        for (String name : names) {
            if (!given.contains(name)) {
                differences.add(name + ": not in Calcite's save");
            }
        }
        for (String name : given) {
            // A backup holds the file it replaced, which is EXPECTED's file.
            String against = isBackup(name) ? original(name) : name;
            if (!names.contains(against)) {
                continue;
            }
            files++;
            lines.taken.clear();
            int before = differences.size();
            try {
                compareFile(name, expected.resolve(against), actual.resolve(name));
            } catch (Exception e) {
                differences.add(name + ": " + e);
            }
            for (LogEvent event : lines.taken) {
                if (event.getLevel().isMoreSpecificThan(org.apache.logging.log4j.Level.WARN)) {
                    differences.add(name + ": vanilla logged " + event.getLevel() + " " + event.getMessage().getFormattedMessage());
                }
            }
            int found = differences.size() - before;
            if (found > PER_FILE) {
                differences.subList(before + PER_FILE, differences.size()).clear();
                differences.add(name + ": and " + (found - PER_FILE) + " more");
            }
        }
    }

    private void compareFile(String name, Path expected, Path actual) throws IOException {
        String file = actual.getFileName().toString();
        if (file.endsWith(".mca")) {
            compareRegion(name, expected, actual);
        } else if (file.endsWith(".dat") || file.endsWith(".dat_old")) {
            CompoundTag a = NbtIo.readCompressed(expected, NbtAccounter.unlimitedHeap());
            CompoundTag b = NbtIo.readCompressed(actual, NbtAccounter.unlimitedHeap());
            if (file.startsWith("level.dat")) {
                withoutLastPlayed(a);
                withoutLastPlayed(b);
            }
            compareTags(name, a, b);
        } else if (file.endsWith(".json")) {
            String a = Files.readString(expected, StandardCharsets.UTF_8);
            String b = Files.readString(actual, StandardCharsets.UTF_8);
            JsonElement ja = JsonParser.parseString(a);
            JsonElement jb = JsonParser.parseString(b);
            if (!ja.equals(jb)) {
                differences.add(name + ": " + diff("", ja, jb));
            } else if (!a.equals(b)) {
                reordered++;
            }
        } else if (!Arrays.equals(Files.readAllBytes(expected), Files.readAllBytes(actual))) {
            differences.add(name + ": the bytes differ");
        }
    }

    private void compareRegion(String name, Path expected, Path actual) throws IOException {
        try (RegionFile a = new RegionFile(info, expected, expected.getParent(), false);
             RegionFile b = new RegionFile(info, actual, actual.getParent(), false)) {
            String[] parts = actual.getFileName().toString().split("\\.");
            int rx = Integer.parseInt(parts[1]);
            int rz = Integer.parseInt(parts[2]);
            for (int i = 0; i < 1024; i++) {
                ChunkPos pos = new ChunkPos(rx * 32 + (i & 31), rz * 32 + (i >> 5));
                CompoundTag ta = read(a, pos);
                CompoundTag tb = read(b, pos);
                String at = name + " [" + pos.x() + ", " + pos.z() + "]";
                if (ta == null && tb == null) {
                    continue;
                }
                chunks++;
                if (ta == null) {
                    differences.add(at + ": only in Calcite's save");
                } else if (tb == null) {
                    differences.add(at + ": not in Calcite's save");
                } else {
                    compareTags(at, ta, tb);
                }
            }
        }
    }

    private static CompoundTag read(RegionFile region, ChunkPos pos) throws IOException {
        try (DataInputStream in = region.getChunkDataInputStream(pos)) {
            return in == null ? null : NbtIo.read(in);
        }
    }

    private void compareTags(String at, CompoundTag a, CompoundTag b) throws IOException {
        if (!a.equals(b)) {
            differences.add(at + ": " + diff("", a, b));
        } else if (!Arrays.equals(bytes(a), bytes(b))) {
            reordered++;
        }
    }

    private static void withoutLastPlayed(CompoundTag root) {
        if (root.get("Data") instanceof CompoundTag data) {
            data.remove("LastPlayed");
        }
    }

    // Where two tags that aren't equal first differ, and how.
    private static String diff(String at, Tag a, Tag b) {
        if (a instanceof CompoundTag ca && b instanceof CompoundTag cb) {
            TreeSet<String> keys = new TreeSet<>(ca.keySet());
            keys.addAll(cb.keySet());
            for (String key : keys) {
                String here = at + "." + key;
                Tag va = ca.get(key);
                Tag vb = cb.get(key);
                if (va == null) {
                    return here + ": only in Calcite's, " + shown(vb.toString());
                }
                if (vb == null) {
                    return here + ": not in Calcite's, " + shown(va.toString());
                }
                if (!va.equals(vb)) {
                    return diff(here, va, vb);
                }
            }
        }
        if (a instanceof ListTag la && b instanceof ListTag lb && la.size() == lb.size()) {
            for (int i = 0; i < la.size(); i++) {
                if (!la.get(i).equals(lb.get(i))) {
                    return diff(at + "[" + i + "]", la.get(i), lb.get(i));
                }
            }
        }
        return (at.isEmpty() ? "the root" : at) + ": " + shown(a.toString()) + " vs " + shown(b.toString());
    }

    // Where two JSON values that aren't equal first differ, and how.
    private static String diff(String at, JsonElement a, JsonElement b) {
        if (a.isJsonObject() && b.isJsonObject()) {
            TreeSet<String> keys = new TreeSet<>(a.getAsJsonObject().keySet());
            keys.addAll(b.getAsJsonObject().keySet());
            for (String key : keys) {
                String here = at + "." + key;
                JsonElement va = a.getAsJsonObject().get(key);
                JsonElement vb = b.getAsJsonObject().get(key);
                if (va == null) {
                    return here + ": only in Calcite's, " + shown(vb.toString());
                }
                if (vb == null) {
                    return here + ": not in Calcite's, " + shown(va.toString());
                }
                if (!va.equals(vb)) {
                    return diff(here, va, vb);
                }
            }
        }
        if (a.isJsonArray() && b.isJsonArray() && a.getAsJsonArray().size() == b.getAsJsonArray().size()) {
            for (int i = 0; i < a.getAsJsonArray().size(); i++) {
                if (!a.getAsJsonArray().get(i).equals(b.getAsJsonArray().get(i))) {
                    return diff(at + "[" + i + "]", a.getAsJsonArray().get(i), b.getAsJsonArray().get(i));
                }
            }
        }
        return (at.isEmpty() ? "the root" : at) + ": " + shown(a.toString()) + " vs " + shown(b.toString());
    }

    private static String shown(String text) {
        return text.length() <= SHOWN ? text : text.substring(0, SHOWN) + "...";
    }

    private static byte[] bytes(CompoundTag tag) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        NbtIo.write(tag, new DataOutputStream(out));
        return out.toByteArray();
    }

    private static boolean isBackup(String name) {
        return name.endsWith("_old");
    }

    private static String original(String name) {
        return name.substring(0, name.length() - "_old".length());
    }

    // Every file under the folder, by its path in it with `/` between folders.
    private static List<String> files(Path root) throws IOException {
        List<String> out = new ArrayList<>();
        try (Stream<Path> walk = Files.walk(root)) {
            walk.filter(Files::isRegularFile).forEach(p -> out.add(root.relativize(p).toString().replace('\\', '/')));
        }
        return out;
    }

    /** What vanilla logs while a file is read. */
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();

        Lines() {
            super("world-check", null, null, true, Property.EMPTY_ARRAY);
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }
    }
}
