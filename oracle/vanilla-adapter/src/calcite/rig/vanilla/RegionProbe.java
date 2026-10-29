package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.chunk.storage.RegionFile;
import net.minecraft.world.level.chunk.storage.RegionFileVersion;
import net.minecraft.world.level.chunk.storage.RegionStorageInfo;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `region`: operations on one region file, `r.0.0.mca`, in a new folder, with vanilla's
 * {@link RegionFile}, each result written to one blob, with what it logged.
 */
final class RegionProbe implements Probe {
    private static final String NAME = "r.0.0.mca";
    private static final RegionStorageInfo INFO = new RegionStorageInfo("probe", Level.OVERWORLD, "chunk");

    @Override
    public String name() {
        return "region";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        JsonArray ops = Args.array(input, "ops");
        Path dir = Files.createTempDirectory("calcite-region");
        Path path = dir.resolve(NAME);
        Lines lines = new Lines(dir.toString() + File.separator);
        Logger logger = (Logger) LogManager.getLogger(RegionFile.class.getName());
        logger.addAppender(lines);
        Region region = null;
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            for (int k = 0; k < ops.size(); k++) {
                JsonArray op = items(ops, k);
                String name = op.get(0).getAsString();
                lines.taken.clear();
                switch (name) {
                    case "put" -> {
                        expect(op, k, 1);
                        Files.write(path, blob(blobs, op, k, 1));
                    }
                    case "put_external" -> {
                        expect(op, k, 3);
                        Files.write(dir.resolve("c." + coordinate(op, k, 1) + "." + coordinate(op, k, 2) + ".mcc"), blob(blobs, op, k, 3));
                    }
                    case "open" -> {
                        expect(op, k, 0);
                        if (region != null) {
                            region.close();
                        }
                        region = new Region(path, dir);
                    }
                    case "write" -> {
                        expect(op, k, 3);
                        byte[] chunk = blob(blobs, op, k, 3);
                        if (chunk.length == 0) {
                            throw new CaseError("operation " + k + ": a chunk needs its compression's byte");
                        }
                        ByteBuffer data = ByteBuffer.allocate(chunk.length + 4);
                        data.putInt(chunk.length);
                        data.put(chunk);
                        data.flip();
                        open(region, k).put(pos(op, k), data);
                    }
                    case "clear" -> {
                        expect(op, k, 2);
                        open(region, k).clear(pos(op, k));
                    }
                    case "has" -> {
                        expect(op, k, 2);
                        boolean has = open(region, k).hasChunk(pos(op, k));
                        writeLines(out, lines);
                        out.writeByte(has ? 1 : 0);
                        continue;
                    }
                    case "read" -> {
                        expect(op, k, 2);
                        byte[] got = null;
                        String thrown = null;
                        try (DataInputStream in = open(region, k).getChunkDataInputStream(pos(op, k))) {
                            if (in != null) {
                                got = in.readAllBytes();
                            }
                        } catch (IOException e) {
                            thrown = e.getClass().getSimpleName();
                        }
                        writeLines(out, lines);
                        if (thrown != null) {
                            out.writeByte(2);
                            message(out, thrown);
                        } else if (got != null) {
                            out.writeByte(1);
                            out.writeInt(got.length);
                            out.write(got);
                        } else {
                            out.writeByte(0);
                        }
                        continue;
                    }
                    case "close" -> {
                        expect(op, k, 0);
                        open(region, k).close();
                        region = null;
                        writeLines(out, lines);
                        files(out, dir);
                        continue;
                    }
                    default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
                }
                writeLines(out, lines);
            }
            out.flush();
            return Result.ok(new JsonObject(), bytes.toByteArray());
        } finally {
            logger.removeAppender(lines);
            if (region != null) {
                region.close();
            }
            try (Stream<Path> walk = Files.walk(dir)) {
                for (Path p : walk.sorted(Comparator.reverseOrder()).toList()) {
                    Files.delete(p);
                }
            }
        }
    }

    /** A region file whose chunks are written as the case gives their bytes, compressed already. */
    private static final class Region extends RegionFile {
        Region(Path path, Path dir) throws IOException {
            super(INFO, path, dir, RegionFileVersion.VERSION_DEFLATE, false);
        }

        void put(ChunkPos pos, ByteBuffer data) throws IOException {
            write(pos, data);
        }
    }

    /**
     * What vanilla's region file logs while an operation runs, with the folder taken out of the
     * paths in it, since each adapter's folder is its own.
     */
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();
        final String folder;

        Lines(String folder) {
            super("region-probe", null, null, true, Property.EMPTY_ARRAY);
            this.folder = folder;
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }
    }

    private static void writeLines(DataOutputStream out, Lines lines) throws IOException {
        out.writeInt(lines.taken.size());
        for (LogEvent event : lines.taken) {
            out.writeByte(switch (event.getLevel().name()) {
                case "WARN" -> 1;
                case "ERROR" -> 2;
                default -> 0;
            });
            message(out, event.getMessage().getFormattedMessage().replace(lines.folder, ""));
        }
    }

    // Every file in the folder by name, the region file's timestamps each 0, or 1 if set.
    private static void files(DataOutputStream out, Path dir) throws IOException {
        List<Path> paths;
        try (Stream<Path> list = Files.list(dir)) {
            paths = list.sorted(Comparator.comparing(p -> p.getFileName().toString())).toList();
        }
        out.writeInt(paths.size());
        for (Path p : paths) {
            String name = p.getFileName().toString();
            byte[] content = Files.readAllBytes(p);
            if (name.equals(NAME)) {
                for (int i = 4096; i + 4 <= Math.min(content.length, 8192); i += 4) {
                    boolean set = content[i] != 0 || content[i + 1] != 0 || content[i + 2] != 0 || content[i + 3] != 0;
                    content[i] = 0;
                    content[i + 1] = 0;
                    content[i + 2] = 0;
                    content[i + 3] = (byte) (set ? 1 : 0);
                }
            }
            message(out, name);
            out.writeInt(content.length);
            out.write(content);
        }
    }

    private static void message(DataOutputStream out, String text) throws IOException {
        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(utf8.length);
        out.write(utf8);
    }

    private static Region open(Region region, int k) {
        if (region == null) {
            throw new CaseError("operation " + k + ": no region file is open");
        }
        return region;
    }

    private static JsonArray items(JsonArray ops, int k) {
        JsonElement op = ops.get(k);
        if (!op.isJsonArray() || op.getAsJsonArray().isEmpty() || !op.getAsJsonArray().get(0).isJsonPrimitive()) {
            throw new CaseError("operation " + k + " must be a non-empty array named by a string");
        }
        return op.getAsJsonArray();
    }

    private static void expect(JsonArray op, int k, int n) {
        if (op.size() != n + 1) {
            throw new CaseError("operation " + k + ": `" + op.get(0).getAsString() + "` takes " + n + " arguments, got " + (op.size() - 1));
        }
    }

    private static int coordinate(JsonArray op, int k, int i) {
        return Args.asInt(op.get(i), "operation " + k + "'s argument " + i);
    }

    // A chunk in the region file, as `x` and `z` from 0 to 31.
    private static ChunkPos pos(JsonArray op, int k) {
        int x = coordinate(op, k, 1);
        int z = coordinate(op, k, 2);
        if (x < 0 || x > 31 || z < 0 || z > 31) {
            throw new CaseError("operation " + k + ": a chunk in r.0.0.mca has x and z from 0 to 31");
        }
        return new ChunkPos(x, z);
    }

    private static byte[] blob(List<byte[]> blobs, JsonArray op, int k, int i) {
        int n = Args.asInt(op.get(i), "operation " + k + "'s argument " + i);
        if (n < 0 || n >= blobs.size()) {
            throw new CaseError("operation " + k + ": there's no blob " + n);
        }
        return blobs.get(n);
    }
}
