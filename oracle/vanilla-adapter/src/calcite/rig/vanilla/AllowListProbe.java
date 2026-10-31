package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.PathMatcher;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;
import net.minecraft.world.level.storage.LevelStorageSource;
import net.minecraft.world.level.validation.DirectoryValidator;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `allow_list`: `allowed_symlinks.txt`, read as a server reads it as it starts, by
 * {@link LevelStorageSource#parseValidator}, then asked about each of a list of link targets, as
 * {@link DirectoryValidator} asks about each link it finds. The targets are paths as this
 * system's {@code Path} writes them, so results differ between Windows and Linux.
 */
final class AllowListProbe implements Probe {
    @Override
    public String name() {
        return "allow_list";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        JsonArray paths = Args.array(input, "paths");
        if (blobs.size() > 1) {
            throw new CaseError("one blob at most, the file");
        }
        List<Path> targets = new ArrayList<>();
        for (int i = 0; i < paths.size(); i++) {
            String text = Args.asString(paths.get(i), "path " + i);
            Path p = Path.of(text);
            if (text.isEmpty() || !p.toString().equals(text)) {
                throw new CaseError("path " + i + ": `" + text + "` isn't a path as Java writes one");
            }
            targets.add(p);
        }
        Path universe = Files.createTempDirectory("calcite-allow");
        Taken taken = new Taken();
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(taken);
        try {
            Path file = universe.resolve("allowed_symlinks.txt");
            if (blobs.size() == 1) {
                Files.write(file, blobs.get(0));
            }
            DirectoryValidator validator = LevelStorageSource.parseValidator(file);
            Field field = DirectoryValidator.class.getDeclaredField("symlinkTargetAllowList");
            field.setAccessible(true);
            PathMatcher matcher = (PathMatcher) field.get(validator);
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            DataOutputStream out = new DataOutputStream(bytes);
            taken.write(out);
            for (Path target : targets) {
                taken.events.clear();
                boolean allowed = matcher.matches(target);
                taken.write(out);
                out.writeByte(allowed ? 1 : 0);
            }
            out.flush();
            return Result.ok(new JsonObject(), bytes.toByteArray());
        } finally {
            root.removeAppender(taken);
            try (Stream<Path> walk = Files.walk(universe)) {
                for (Path p : walk.sorted(Comparator.reverseOrder()).toList()) {
                    Files.delete(p);
                }
            }
        }
    }

    // What's logged, by level and message, as `world_folder` writes it.
    private static final class Taken extends AbstractAppender {
        final List<LogEvent> events = new ArrayList<>();

        Taken() {
            super("allow-list-probe", null, null, true, Property.EMPTY_ARRAY);
            start();
        }

        @Override
        public void append(LogEvent event) {
            events.add(event.toImmutable());
        }

        void write(DataOutputStream out) throws IOException {
            out.writeInt(events.size());
            for (LogEvent event : events) {
                out.writeByte(switch (event.getLevel().name()) {
                    case "WARN" -> 1;
                    case "ERROR" -> 2;
                    default -> 0;
                });
                byte[] utf8 = event.getMessage().getFormattedMessage().getBytes(StandardCharsets.UTF_8);
                out.writeInt(utf8.length);
                out.write(utf8);
            }
            events.clear();
        }
    }
}
