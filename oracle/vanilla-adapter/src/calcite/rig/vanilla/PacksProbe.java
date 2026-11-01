package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import net.minecraft.IdentifierException;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.repository.Pack;
import net.minecraft.server.packs.repository.PackRepository;
import net.minecraft.server.packs.repository.PackSource;
import net.minecraft.server.packs.repository.ServerPacksSource;
import net.minecraft.server.packs.resources.MultiPackResourceManager;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.world.flag.FeatureFlagSet;
import net.minecraft.world.flag.FeatureFlags;
import net.minecraft.world.level.DataPackConfig;
import net.minecraft.world.level.WorldDataConfiguration;
import net.minecraft.world.level.storage.LevelStorageSource;
import net.minecraft.world.level.validation.DirectoryValidator;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `packs`: a world's data packs found and picked as a server starting finds and picks them, in a
 * world's folder, `world`, in a new folder of its own. Operations make the world's
 * `datapacks` folder and `allowed_symlinks.txt` as `world_folder`'s do, then `pick` reads the
 * allow list with {@link LevelStorageSource#parseValidator}, makes the repository with
 * {@link ServerPacksSource#createPackRepository(Path, DirectoryValidator)} and picks its packs
 * with {@link MinecraftServer#configurePackRepository}, and `list` lists the picked packs' files
 * with a {@link MultiPackResourceManager} over them, as the server's resources are made. Each
 * result goes into one blob, after what was logged.
 */
final class PacksProbe implements Probe {
    @Override
    public String name() {
        return "packs";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        JsonArray ops = Args.array(input, "ops");
        Path universe = Files.createTempDirectory("calcite-packs");
        Path world = universe.resolve("world");
        Files.createDirectories(world);
        Lines lines = new Lines(universe.toString() + File.separator);
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        PackRepository repository = null;
        MultiPackResourceManager manager = null;
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
                        Files.write(file, blob(blobs, op, k, 2));
                        lines.write(out);
                    }
                    case "dir" -> {
                        expect(op, k, 1);
                        Files.createDirectories(inside(world, op, k));
                        lines.write(out);
                    }
                    case "link" -> {
                        expect(op, k, 2);
                        Path link = inside(world, op, k);
                        String target = Args.asString(op.get(2), "operation " + k + "'s target").replace("<folder>", lines.folder);
                        Path to = Path.of(target);
                        if (target.isEmpty() || !to.toString().equals(target)) {
                            throw new CaseError("operation " + k + ": `" + target + "` isn't a path as Java writes one");
                        }
                        Files.createDirectories(link.getParent());
                        Files.createSymbolicLink(link, to);
                        lines.write(out);
                    }
                    case "allow" -> {
                        expect(op, k, 1);
                        Files.write(universe.resolve("allowed_symlinks.txt"), replaced(blob(blobs, op, k, 1), lines.folder));
                        lines.write(out);
                    }
                    case "pick" -> {
                        expect(op, k, 1);
                        if (repository != null) {
                            throw new CaseError("operation " + k + ": the packs are picked already");
                        }
                        if (!op.get(1).isJsonObject()) {
                            throw new CaseError("operation " + k + "'s setup must be an object");
                        }
                        JsonObject setup = op.get(1).getAsJsonObject();
                        List<String> enabled = strings(Args.array(setup, "enabled"), "`enabled`");
                        List<String> disabled = strings(Args.array(setup, "disabled"), "`disabled`");
                        List<Identifier> flags = new ArrayList<>();
                        for (String f : strings(Args.array(setup, "features"), "`features`")) {
                            try {
                                flags.add(Identifier.parse(f));
                            } catch (IdentifierException e) {
                                throw new CaseError("operation " + k + ": `" + f + "` isn't a feature flag's ID");
                            }
                        }
                        int at = k;
                        FeatureFlagSet features = FeatureFlags.REGISTRY.fromNames(flags, unknown -> {
                            throw new CaseError("operation " + at + ": no feature flag `" + unknown + "`");
                        });
                        boolean init = bool(setup, "init");
                        boolean safe = bool(setup, "safe");
                        // As `Main` makes them: the validator as the level storage is made, the
                        // repository once the world's folder is open, then the packs picked.
                        DirectoryValidator validator = LevelStorageSource.parseValidator(universe.resolve("allowed_symlinks.txt"));
                        repository = ServerPacksSource.createPackRepository(world.resolve("datapacks"), validator);
                        WorldDataConfiguration picked = MinecraftServer.configurePackRepository(
                            repository, new WorldDataConfiguration(new DataPackConfig(enabled, disabled), features), init, safe);
                        lines.write(out);
                        out.writeInt(repository.getAvailablePacks().size());
                        for (Pack pack : repository.getAvailablePacks()) {
                            text(out, pack.getId());
                            out.writeByte(source(pack.getPackSource()));
                            out.writeByte(pack.getCompatibility().ordinal());
                            names(out, pack.getRequestedFeatures());
                            JsonElement description = ComponentSerialization.CODEC.encodeStart(JsonOps.INSTANCE, pack.getDescription()).getOrThrow();
                            text(out, description.toString());
                        }
                        strings(out, picked.dataPacks().getEnabled());
                        strings(out, picked.dataPacks().getDisabled());
                        names(out, picked.enabledFeatures());
                    }
                    case "list" -> {
                        expect(op, k, 2);
                        if (repository == null) {
                            throw new CaseError("operation " + k + ": the packs aren't picked");
                        }
                        String directory = Args.asString(op.get(1), "operation " + k + "'s folder");
                        String suffix = Args.asString(op.get(2), "operation " + k + "'s suffix");
                        if (manager == null) {
                            manager = new MultiPackResourceManager(PackType.SERVER_DATA, repository.openAllSelected());
                        }
                        Map<Identifier, Resource> found = manager.listResources(directory, id -> id.getPath().endsWith(suffix));
                        lines.write(out);
                        out.writeInt(found.size());
                        for (Map.Entry<Identifier, Resource> e : found.entrySet()) {
                            text(out, e.getKey().toString());
                            text(out, e.getValue().sourcePackId());
                            byte[] content;
                            try (InputStream in = e.getValue().open()) {
                                content = in.readAllBytes();
                            }
                            out.writeInt(content.length);
                            out.write(content);
                        }
                    }
                    default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
                }
            }
            out.flush();
            return Result.ok(new JsonObject(), bytes.toByteArray());
        } finally {
            root.removeAppender(lines);
            if (manager != null) {
                manager.close();
            }
            try (Stream<Path> walk = Files.walk(universe)) {
                for (Path p : walk.sorted(Comparator.reverseOrder()).toList()) {
                    Files.delete(p);
                }
            }
        }
    }

    // A pack's source as a byte: 0 built in, 1 a feature pack, 2 the world's.
    private static int source(PackSource source) {
        if (source == PackSource.BUILT_IN) {
            return 0;
        }
        if (source == PackSource.FEATURE) {
            return 1;
        }
        if (source == PackSource.WORLD) {
            return 2;
        }
        throw new IllegalStateException("a pack from " + source);
    }

    // The flags' IDs, in the order `toNames` gives them: an `int` count, then each.
    private static void names(DataOutputStream out, FeatureFlagSet set) throws IOException {
        List<String> ids = new ArrayList<>();
        for (Identifier id : FeatureFlags.REGISTRY.toNames(set)) {
            ids.add(id.toString());
        }
        strings(out, ids);
    }

    private static void strings(DataOutputStream out, List<String> list) throws IOException {
        out.writeInt(list.size());
        for (String s : list) {
            text(out, s);
        }
    }

    private static List<String> strings(JsonArray array, String what) {
        List<String> out = new ArrayList<>();
        for (JsonElement e : array) {
            out.add(Args.asString(e, what + "'s item"));
        }
        return out;
    }

    private static boolean bool(JsonObject setup, String name) {
        JsonElement value = Args.field(setup, name);
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("`" + name + "` must be true or false");
        }
        return value.getAsBoolean();
    }

    private static byte[] blob(List<byte[]> blobs, JsonArray op, int k, int at) {
        int blob = Args.asInt(op.get(at), "operation " + k + "'s blob");
        if (blob < 0 || blob >= blobs.size()) {
            throw new CaseError("operation " + k + ": no blob " + blob);
        }
        return blobs.get(blob);
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

    // The bytes with each `<folder>` in them replaced by the universe's path and a separator.
    private static byte[] replaced(byte[] bytes, String folder) {
        byte[] mark = "<folder>".getBytes(StandardCharsets.UTF_8);
        byte[] with = folder.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int i = 0;
        while (i < bytes.length) {
            boolean here = i + mark.length <= bytes.length;
            for (int j = 0; here && j < mark.length; j++) {
                here = bytes[i + j] == mark[j];
            }
            if (here) {
                out.writeBytes(with);
                i += mark.length;
            } else {
                out.write(bytes[i]);
                i++;
            }
        }
        return out.toByteArray();
    }

    private static void text(DataOutputStream out, String text) throws IOException {
        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(utf8.length);
        out.write(utf8);
    }

    /**
     * What vanilla logs while an operation runs: each line's message, then, if it was logged with
     * an exception, a line break and the exception as its `toString` writes it, with the folder
     * each run's world is in taken out and `/` between names.
     */
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();
        final String folder;

        Lines(String folder) {
            super("packs-probe", null, null, true, Property.EMPTY_ARRAY);
            this.folder = folder;
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }

        String normal(String text) {
            return text.replace(folder, "").replace(File.separatorChar, '/');
        }

        void write(DataOutputStream out) throws IOException {
            out.writeInt(taken.size());
            for (LogEvent event : taken) {
                out.writeByte(switch (event.getLevel().name()) {
                    case "WARN" -> 1;
                    case "ERROR" -> 2;
                    default -> 0;
                });
                String message = event.getMessage().getFormattedMessage();
                Throwable thrown = event.getThrown();
                text(out, normal(thrown == null ? message : message + "\n" + thrown));
            }
        }
    }
}
