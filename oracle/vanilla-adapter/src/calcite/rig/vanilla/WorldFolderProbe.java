package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.serialization.Dynamic;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;
import java.util.zip.GZIPInputStream;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.util.datafix.DataFixers;
import net.minecraft.world.level.storage.LevelStorageSource;
import net.minecraft.world.level.storage.LevelSummary;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `world_folder`: operations on a world's folder, `world`, in a new folder of its own, with
 * vanilla's {@link LevelStorageSource} and its access: opening and locking it, reading
 * `level.dat` with its fallback, checking the version as `Main` does, saving it, and the files
 * left. Each result goes into one blob, after what was logged.
 */
final class WorldFolderProbe implements Probe {
    @Override
    public String name() {
        return "world_folder";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        JsonArray ops = Args.array(input, "ops");
        // Built before anything is logged, since building it logs.
        DataFixers.getDataFixer();
        Path universe = Files.createTempDirectory("calcite-world");
        Path world = universe.resolve("world");
        Lines lines = new Lines(universe.toString() + File.separator);
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        LevelStorageSource.LevelStorageAccess access = null;
        Dynamic<?> data = null;
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            for (int k = 0; k < ops.size(); k++) {
                if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                    throw new CaseError("operation " + k + " isn't a list with its name first");
                }
                JsonArray op = ops.get(k).getAsJsonArray();
                String name = Args.asString(op.get(0), "operation " + k);
                lines.taken.clear();
                switch (name) {
                    case "put" -> {
                        expect(op, k, 2);
                        Path file = inside(world, op, k);
                        Files.createDirectories(file.getParent());
                        int blob = Args.asInt(op.get(2), "operation " + k + "'s blob");
                        if (blob < 0 || blob >= blobs.size()) {
                            throw new CaseError("operation " + k + ": no blob " + blob);
                        }
                        Files.write(file, blobs.get(blob));
                        lines.write(out);
                    }
                    case "dir" -> {
                        expect(op, k, 1);
                        Files.createDirectories(inside(world, op, k));
                        lines.write(out);
                    }
                    case "open" -> {
                        expect(op, k, 0);
                        if (access != null) {
                            throw new CaseError("operation " + k + ": the folder is open already");
                        }
                        String thrown = null;
                        try {
                            access = LevelStorageSource.createDefault(universe).validateAndCreateAccess("world");
                        } catch (Exception e) {
                            thrown = e.getClass().getName() + ": " + e.getMessage();
                        }
                        lines.write(out);
                        if (thrown == null) {
                            out.writeByte(1);
                        } else {
                            out.writeByte(0);
                            text(out, lines.normal(thrown));
                        }
                    }
                    case "has" -> {
                        expect(op, k, 0);
                        boolean has = open(access, k).hasWorldData();
                        lines.write(out);
                        out.writeByte(has ? 1 : 0);
                    }
                    case "load" -> {
                        expect(op, k, 0);
                        LevelStorageSource.LevelStorageAccess a = open(access, k);
                        data = null;
                        try {
                            data = a.getUnfixedDataTagWithFallback();
                        } catch (Exception e) {
                            // `Main` stops here, with its own line.
                        }
                        lines.write(out);
                        if (data == null) {
                            out.writeByte(0);
                        } else {
                            out.writeByte(1);
                            ByteArrayOutputStream nbt = new ByteArrayOutputStream();
                            NbtIo.write((CompoundTag) data.getValue(), new DataOutputStream(nbt));
                            out.writeInt(nbt.size());
                            out.write(nbt.toByteArray());
                        }
                    }
                    case "check" -> {
                        expect(op, k, 0);
                        LevelStorageSource.LevelStorageAccess a = open(access, k);
                        Dynamic<?> d = loaded(data, k);
                        LevelSummary summary = null;
                        String thrown = null;
                        try {
                            summary = a.fixAndGetSummaryFromTag(d);
                        } catch (Exception e) {
                            thrown = e.getClass().getName() + ": " + e.getMessage();
                        }
                        lines.write(out);
                        if (thrown != null) {
                            out.writeByte(0);
                            text(out, thrown);
                        } else if (summary.requiresManualConversion()) {
                            out.writeByte(1);
                        } else if (!summary.isCompatible()) {
                            out.writeByte(2);
                        } else {
                            out.writeByte(3);
                            out.writeInt(NbtUtils.getDataVersion(d));
                        }
                    }
                    case "save" -> {
                        expect(op, k, 0);
                        open(access, k).saveLevelData(loaded(data, k));
                        lines.write(out);
                    }
                    case "close" -> {
                        expect(op, k, 0);
                        open(access, k).close();
                        access = null;
                        lines.write(out);
                        files(out, world, lines);
                    }
                    default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
                }
            }
            out.flush();
            return Result.ok(new JsonObject(), bytes.toByteArray());
        } finally {
            root.removeAppender(lines);
            if (access != null) {
                access.close();
            }
            try (Stream<Path> walk = Files.walk(universe)) {
                for (Path p : walk.sorted(Comparator.reverseOrder()).toList()) {
                    Files.delete(p);
                }
            }
        }
    }

    private static void expect(JsonArray op, int k, int args) {
        if (op.size() != args + 1) {
            throw new CaseError("operation " + k + " takes " + args + " arguments");
        }
    }

    // The file the operation names in the world's folder, which mustn't leave it.
    private static Path inside(Path world, JsonArray op, int k) {
        String name = Args.asString(op.get(1), "operation " + k + "'s name");
        Path file = world.resolve(name).normalize();
        if (name.isEmpty() || !file.startsWith(world) || file.equals(world)) {
            throw new CaseError("operation " + k + ": `" + name + "` isn't in the world's folder");
        }
        return file;
    }

    private static LevelStorageSource.LevelStorageAccess open(LevelStorageSource.LevelStorageAccess access, int k) {
        if (access == null) {
            throw new CaseError("operation " + k + ": the folder isn't open");
        }
        return access;
    }

    private static Dynamic<?> loaded(Dynamic<?> data, int k) {
        if (data == null) {
            throw new CaseError("operation " + k + ": nothing was loaded");
        }
        return data;
    }

    // Every file and folder in the world's folder, by path, sorted: an `int` count, then for each
    // its path as a message, then a byte, 0 for a file, 1 for a folder and 2 for a gzipped file
    // that inflates, and a file's `int` length and bytes, what it inflates to for a gzipped one.
    // No two deflaters write the same bytes, so a gzipped file is compared by what it holds.
    private static void files(DataOutputStream out, Path world, Lines lines) throws IOException {
        List<Path> paths;
        try (Stream<Path> walk = Files.walk(world)) {
            paths = walk.filter(p -> !p.equals(world)).toList();
        }
        List<String[]> named = new ArrayList<>();
        for (Path p : paths) {
            named.add(new String[] {lines.normal(world.relativize(p).toString()), p.toString()});
        }
        named.sort(Comparator.comparing(n -> n[0]));
        out.writeInt(named.size());
        for (String[] n : named) {
            text(out, n[0]);
            Path p = Path.of(n[1]);
            if (Files.isDirectory(p)) {
                out.writeByte(1);
            } else {
                byte[] content = Files.readAllBytes(p);
                byte[] inflated = null;
                if (content.length >= 2 && (content[0] & 0xff) == 0x1f && (content[1] & 0xff) == 0x8b) {
                    try (GZIPInputStream in = new GZIPInputStream(new ByteArrayInputStream(content))) {
                        inflated = in.readAllBytes();
                    } catch (IOException e) {
                        inflated = null;
                    }
                }
                out.writeByte(inflated == null ? 0 : 2);
                byte[] shown = inflated == null ? content : inflated;
                out.writeInt(shown.length);
                out.write(shown);
            }
        }
    }

    private static void text(DataOutputStream out, String text) throws IOException {
        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(utf8.length);
        out.write(utf8);
    }

    /**
     * What vanilla logs while an operation runs, with paths made the same everywhere: the
     * folder each run's world is in taken out, `/` between names, and the clock's time and the
     * random number in names written as `<time>` and `<n>`.
     */
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();
        final String folder;

        Lines(String folder) {
            super("world-folder-probe", null, null, true, Property.EMPTY_ARRAY);
            this.folder = folder;
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }

        String normal(String text) {
            return text.replace(folder, "")
                .replace(File.separatorChar, '/')
                .replaceAll("_corrupted_\\d{4}-\\d{2}-\\d{2}_\\d{2}-\\d{2}-\\d{2}", "_corrupted_<time>")
                .replaceAll("level\\d+\\.dat", "level<n>.dat");
        }

        void write(DataOutputStream out) throws IOException {
            out.writeInt(taken.size());
            for (LogEvent event : taken) {
                out.writeByte(switch (event.getLevel().name()) {
                    case "WARN" -> 1;
                    case "ERROR" -> 2;
                    default -> 0;
                });
                text(out, normal(event.getMessage().getFormattedMessage()));
            }
        }
    }
}
