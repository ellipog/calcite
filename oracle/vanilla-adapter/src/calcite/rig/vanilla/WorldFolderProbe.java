package calcite.rig.vanilla;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonIOException;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.mojang.authlib.GameProfile;
import com.mojang.datafixers.util.Pair;
import com.mojang.logging.LogUtils;
import com.mojang.serialization.Codec;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.Dynamic;
import com.mojang.serialization.DynamicOps;
import com.mojang.serialization.JsonOps;
import java.io.DataInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletionException;
import java.util.stream.Stream;
import java.util.zip.GZIPInputStream;
import net.minecraft.IdentifierException;
import net.minecraft.SharedConstants;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.PlayerAdvancements;
import net.minecraft.server.dedicated.DedicatedPlayerList;
import net.minecraft.server.dedicated.DedicatedServer;
import net.minecraft.server.players.NameAndId;
import net.minecraft.server.players.PlayerList;
import net.minecraft.stats.ServerStatsCounter;
import net.minecraft.util.FileUtil;
import net.minecraft.util.StrictJsonParser;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.util.datafix.DataFixers;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.saveddata.SavedDataType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.level.storage.LevelStorageSource;
import net.minecraft.world.level.storage.LevelSummary;
import net.minecraft.world.level.storage.PlayerDataStorage;
import net.minecraft.world.level.storage.SavedDataStorage;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `world_folder`: operations on a world's folder, `world`, in a new folder of its own, with
 * vanilla's {@link LevelStorageSource} and its access: opening and locking it, reading
 * `level.dat` with its fallback, checking the version as `Main` does, saving it, reading a
 * player's data as they join, reading and writing saved data with {@link SavedDataStorage},
 * reading and writing players' advancements and statistics as {@link PlayerAdvancements} and
 * {@link ServerStatsCounter} do, finding a player's statistics with {@link PlayerList}'s
 * `locateStatsFile`, and the files left. Each result goes into one blob, after what was logged.
 */
final class WorldFolderProbe implements Probe {
    @Override
    public String name() {
        return "world_folder";
    }

    @Override
    public int version() {
        return 4;
    }

    // Logs as `PlayerAdvancements` and `ServerStatsCounter` log, for the parts of them run here.
    private static final org.slf4j.Logger LOGGER = LogUtils.getLogger();

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
        PlayerDataStorage players = null;
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
                    case "player_load" -> {
                        expect(op, k, 2);
                        LevelStorageSource.LevelStorageAccess a = open(access, k);
                        UUID id;
                        try {
                            id = UUID.fromString(Args.asString(op.get(1), "operation " + k + "'s UUID"));
                        } catch (IllegalArgumentException e) {
                            throw new CaseError("operation " + k + ": the UUID isn't one");
                        }
                        String player = Args.asString(op.get(2), "operation " + k + "'s name");
                        if (players == null) {
                            // As the server makes it as it starts, which makes `players/data`.
                            players = new PlayerDataStorage(a, DataFixers.getDataFixer());
                        }
                        Optional<CompoundTag> tag = players.load(new NameAndId(id, player));
                        lines.write(out);
                        if (tag.isEmpty()) {
                            out.writeByte(0);
                        } else {
                            out.writeByte(1);
                            ByteArrayOutputStream nbt = new ByteArrayOutputStream();
                            NbtIo.write(tag.get(), new DataOutputStream(nbt));
                            out.writeInt(nbt.size());
                            out.write(nbt.toByteArray());
                        }
                    }
                    case "saved_load" -> {
                        expect(op, k, 2);
                        SavedDataStorage storage = saved(open(access, k), op, k);
                        Raw raw = storage.get(type(op, k));
                        lines.write(out);
                        if (raw == null) {
                            out.writeByte(0);
                        } else if (raw.tag == null) {
                            out.writeByte(2);
                        } else {
                            out.writeByte(1);
                            ByteArrayOutputStream nbt = new ByteArrayOutputStream();
                            NbtIo.writeAnyTag(raw.tag, new DataOutputStream(nbt));
                            out.writeInt(nbt.size());
                            out.write(nbt.toByteArray());
                        }
                    }
                    case "saved_save" -> {
                        expect(op, k, 3);
                        SavedDataStorage storage = saved(open(access, k), op, k);
                        SavedDataType<Raw> type = type(op, k);
                        int blob = Args.asInt(op.get(3), "operation " + k + "'s blob");
                        if (blob < 0 || blob >= blobs.size()) {
                            throw new CaseError("operation " + k + ": no blob " + blob);
                        }
                        Tag tag;
                        try {
                            tag = NbtIo.readAnyTag(new DataInputStream(new ByteArrayInputStream(blobs.get(blob))), NbtAccounter.unlimitedHeap());
                        } catch (IOException e) {
                            throw new CaseError("operation " + k + ": blob " + blob + " isn't a tag");
                        }
                        storage.set(type, new Raw(tag));
                        String thrown = null;
                        try {
                            storage.saveAndJoin();
                        } catch (CompletionException e) {
                            Throwable cause = e.getCause();
                            thrown = cause.getClass().getName() + ": " + cause.getMessage();
                        }
                        lines.write(out);
                        if (thrown == null) {
                            out.writeByte(0);
                        } else {
                            out.writeByte(1);
                            text(out, lines.normal(thrown));
                        }
                    }
                    case "progress_load" -> {
                        expect(op, k, 2);
                        boolean stats = kind(op, k);
                        Path file = progressFile(open(access, k), stats, op, k);
                        JsonElement json = stats ? readStats(file) : readAdvancements(file);
                        lines.write(out);
                        if (json == null) {
                            out.writeByte(0);
                        } else {
                            out.writeByte(1);
                            text(out, json.toString());
                            Integer version;
                            try {
                                version = stats ? NbtUtils.getDataVersion(new Dynamic<>(JsonOps.INSTANCE, json), 1343) : advancementsVersion(json);
                            } catch (NumberFormatException e) {
                                version = null;
                            }
                            if (version == null) {
                                out.writeByte(0);
                            } else {
                                out.writeByte(1);
                                out.writeInt(version);
                            }
                        }
                    }
                    case "progress_save" -> {
                        expect(op, k, 3);
                        boolean stats = kind(op, k);
                        Path file = progressFile(open(access, k), stats, op, k);
                        int blob = Args.asInt(op.get(3), "operation " + k + "'s blob");
                        if (blob < 0 || blob >= blobs.size()) {
                            throw new CaseError("operation " + k + ": no blob " + blob);
                        }
                        JsonElement members = JsonParser.parseString(new String(blobs.get(blob), StandardCharsets.UTF_8));
                        if (!members.isJsonObject()) {
                            throw new CaseError("operation " + k + ": blob " + blob + " isn't a JSON object");
                        }
                        if (stats) {
                            saveStats(file, members);
                        } else {
                            saveAdvancements(file, members);
                        }
                        lines.write(out);
                    }
                    case "stats_locate" -> {
                        expect(op, k, 2);
                        UUID id;
                        try {
                            id = UUID.fromString(Args.asString(op.get(1), "operation " + k + "'s UUID"));
                        } catch (IllegalArgumentException e) {
                            throw new CaseError("operation " + k + ": the UUID isn't one");
                        }
                        String player = Args.asString(op.get(2), "operation " + k + "'s name");
                        Path found = locateStatsFile(open(access, k), new GameProfile(id, player));
                        lines.write(out);
                        text(out, lines.normal(found.toString()));
                    }
                    case "close" -> {
                        expect(op, k, 0);
                        open(access, k).close();
                        access = null;
                        players = null;
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

    // Whether the operation is on statistics rather than advancements.
    private static boolean kind(JsonArray op, int k) {
        String kind = Args.asString(op.get(1), "operation " + k + "'s kind");
        return switch (kind) {
            case "advancements" -> false;
            case "stats" -> true;
            default -> throw new CaseError("operation " + k + ": `" + kind + "` isn't advancements or stats");
        };
    }

    // `<uuid>.json` in the world's advancements or statistics, for the operation's UUID, which
    // is any name here, since what's in the folder is what's tried.
    private static Path progressFile(LevelStorageSource.LevelStorageAccess access, boolean stats, JsonArray op, int k) {
        String uuid = Args.asString(op.get(2), "operation " + k + "'s UUID");
        if (uuid.isEmpty() || uuid.contains("/") || uuid.contains("\\") || uuid.contains("..") || uuid.contains(":")) {
            throw new CaseError("operation " + k + ": `" + uuid + "` isn't a name in the folder");
        }
        return access.getLevelPath(stats ? LevelResource.PLAYER_STATS_DIR : LevelResource.PLAYER_ADVANCEMENTS_DIR).resolve(uuid + ".json");
    }

    // What `PlayerAdvancements.load` reads before its codec, with its lines.
    private static JsonElement readAdvancements(Path path) {
        if (Files.isRegularFile(path)) {
            try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
                return StrictJsonParser.parse(reader);
            } catch (IOException | JsonIOException e) {
                LOGGER.error("Couldn't access player advancements in {}", path, e);
            } catch (JsonParseException e) {
                LOGGER.error("Couldn't parse player advancements in {}", path, e);
            }
        }
        return null;
    }

    // What `ServerStatsCounter`'s constructor reads before `parse`, with its lines.
    private static JsonElement readStats(Path file) {
        if (Files.isRegularFile(file)) {
            try (Reader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) {
                return StrictJsonParser.parse(reader);
            } catch (IOException e) {
                LOGGER.error("Couldn't read statistics file {}", file, e);
            } catch (JsonParseException e) {
                LOGGER.error("Couldn't parse statistics file {}", file, e);
            }
        }
        return null;
    }

    // The version `DataFixTypes.wrapCodec` reads advancements as from.
    private static int advancementsVersion(JsonElement json) {
        JsonOps ops = JsonOps.INSTANCE;
        return ops.get(json, "DataVersion").flatMap(ops::getNumberValue).map(Number::intValue).result().orElse(1343);
    }

    // `PlayerAdvancements.save`, given what its codec encodes: the version merged in as
    // `wrapCodec` merges it, then written with its `GSON`.
    private static void saveAdvancements(Path path, JsonElement members) throws Exception {
        JsonOps ops = JsonOps.INSTANCE;
        JsonElement json = ops.mergeToMap(members, ops.createString("DataVersion"), ops.createInt(SharedConstants.getCurrentVersion().dataVersion().version())).getOrThrow();
        Gson gson = gson(PlayerAdvancements.class);
        try {
            FileUtil.createDirectoriesSafe(path.getParent());
            try (Writer outputWriter = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
                gson.toJson(json, gson.newJsonWriter(outputWriter));
            }
        } catch (IOException | JsonIOException e) {
            LOGGER.error("Couldn't save player advancements to {}", path, e);
        }
    }

    // `ServerStatsCounter.save`, given what its codec encodes, put in an object as `toJson` puts
    // it, and written with its `GSON`.
    private static void saveStats(Path file, JsonElement stats) throws Exception {
        JsonObject result = new JsonObject();
        result.add("stats", stats);
        result.addProperty("DataVersion", SharedConstants.getCurrentVersion().dataVersion().version());
        Gson gson = gson(ServerStatsCounter.class);
        try {
            FileUtil.createDirectoriesSafe(file.getParent());
            try (Writer writer = Files.newBufferedWriter(file, StandardCharsets.UTF_8)) {
                gson.toJson(result, gson.newJsonWriter(writer));
            }
        } catch (IOException | JsonIOException e) {
            LOGGER.error("Couldn't save stats to {}", file, e);
        }
    }

    // The class's own `GSON`.
    private static Gson gson(Class<?> owner) throws Exception {
        Field field = owner.getDeclaredField("GSON");
        field.setAccessible(true);
        return (Gson) field.get(null);
    }

    // `PlayerList.locateStatsFile` itself, on a player list and server made without their
    // constructors, which hold only what it reads: the server, and the server's folder.
    private static Path locateStatsFile(LevelStorageSource.LevelStorageAccess access, GameProfile profile) throws Exception {
        // `sun.misc.Unsafe`, found by name, since the build takes no warnings.
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field theUnsafe = unsafeClass.getDeclaredField("theUnsafe");
        theUnsafe.setAccessible(true);
        Object unsafe = theUnsafe.get(null);
        Method allocate = unsafeClass.getMethod("allocateInstance", Class.class);
        DedicatedServer server = (DedicatedServer) allocate.invoke(unsafe, DedicatedServer.class);
        Field storage = MinecraftServer.class.getDeclaredField("storageSource");
        storage.setAccessible(true);
        storage.set(server, access);
        DedicatedPlayerList list = (DedicatedPlayerList) allocate.invoke(unsafe, DedicatedPlayerList.class);
        Field owner = PlayerList.class.getDeclaredField("server");
        owner.setAccessible(true);
        owner.set(list, server);
        Method locate = PlayerList.class.getDeclaredMethod("locateStatsFile", GameProfile.class);
        locate.setAccessible(true);
        try {
            return (Path) locate.invoke(list, profile);
        } catch (InvocationTargetException e) {
            throw new CaseError("locateStatsFile threw " + e.getCause());
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

    // A `SavedDataStorage` for the folder the operation names: the world's `data` for `""`, or
    // that dimension's. A new one each time, so nothing read before is kept.
    private static SavedDataStorage saved(LevelStorageSource.LevelStorageAccess access, JsonArray op, int k) {
        String folder = Args.asString(op.get(1), "operation " + k + "'s folder");
        Path path;
        if (folder.isEmpty()) {
            path = access.getLevelPath(LevelResource.DATA);
        } else {
            try {
                path = access.getDimensionPath(ResourceKey.create(Registries.DIMENSION, Identifier.parse(folder))).resolve("data");
            } catch (IdentifierException e) {
                throw new CaseError("operation " + k + ": `" + folder + "` isn't a dimension");
            }
        }
        return new SavedDataStorage(path, DataFixers.getDataFixer(), RegistryAccess.EMPTY);
    }

    // A saved data type named by the operation, whose codec keeps its `data` as it is.
    private static SavedDataType<Raw> type(JsonArray op, int k) {
        Identifier id;
        try {
            id = Identifier.parse(Args.asString(op.get(2), "operation " + k + "'s ID"));
        } catch (IdentifierException e) {
            throw new CaseError("operation " + k + ": the ID isn't one");
        }
        return new SavedDataType<>(id, () -> new Raw(null), RAW, DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);
    }

    // Saved data that's what was read, `null` for a file with no `data`.
    private static final class Raw extends SavedData {
        final Tag tag;

        Raw(Tag tag) {
            this.tag = tag;
        }
    }

    private static final Codec<Raw> RAW = new Codec<>() {
        @Override
        public <T> DataResult<Pair<Raw, T>> decode(DynamicOps<T> ops, T input) {
            return DataResult.success(Pair.of(new Raw((Tag) input), ops.empty()));
        }

        @Override
        @SuppressWarnings("unchecked")
        public <T> DataResult<T> encode(Raw input, DynamicOps<T> ops, T prefix) {
            return DataResult.success((T) input.tag);
        }
    };

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
