package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import com.mojang.serialization.Codec;
import com.mojang.serialization.Dynamic;
import com.mojang.serialization.DynamicOps;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.stream.Stream;
import net.minecraft.core.RegistryAccess;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.Tag;
import net.minecraft.nbt.TagParser;
import net.minecraft.resources.RegistryOps;
import net.minecraft.util.ProblemReporter;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.util.datafix.DataFixers;
import net.minecraft.world.entity.ai.village.poi.PoiSection;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.storage.ChunkIOErrorReporter;
import net.minecraft.world.level.chunk.storage.EntityStorage;
import net.minecraft.world.level.chunk.storage.RegionStorageInfo;
import net.minecraft.world.level.chunk.storage.SectionStorage;
import net.minecraft.world.level.chunk.storage.SimpleRegionStorage;
import net.minecraft.world.level.storage.TagValueInput;
import net.minecraft.world.level.storage.ValueInput;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `entities_poi`: a chunk of a world's `entities/` or `poi/` folder, given as SNBT, as vanilla reads
 * and writes it.
 *
 * <p>`entities_load` reads it as {@link EntityStorage#loadEntities} does before the entities
 * themselves are made, which needs a level: the `Position` checked, the tag upgraded, and the
 * `Entities` list read through {@link TagValueInput} in a {@link ProblemReporter.ScopedCollector}
 * on `EntityStorage`'s own logger, each step vanilla's own. `entities_save` puts saved entities in
 * a chunk's tag as {@link EntityStorage#storeEntities} does. `poi` reads it with
 * {@link SectionStorage}'s own `PackedChunk.parse` and `unpackChunk`, with {@link PoiSection}'s
 * codec, as {@code PoiManager} does, and writes it back with its own `writeChunk`.
 */
final class EntitiesPoiProbe implements Probe {
    private static final ChunkIOErrorReporter NO_REPORTS = new ChunkIOErrorReporter() {
        @Override
        public void reportChunkLoadFailure(Throwable throwable, RegionStorageInfo storageInfo, ChunkPos pos) {
        }

        @Override
        public void reportChunkSaveFailure(Throwable throwable, RegionStorageInfo storageInfo, ChunkPos pos) {
        }
    };

    @Override
    public String name() {
        return "entities_poi";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`entities_poi` takes no blobs");
        }
        String op = Args.string(input, "op");
        ChunkPos pos = new ChunkPos(Args.asInt(Args.field(input, "x"), "`x`"), Args.asInt(Args.field(input, "z"), "`z`"));
        CompoundTag tag = null;
        if (input.has("snbt")) {
            try {
                // A copy, since the SNBT parser gives every `{}` it reads as one compound,
                // which upgrading a chunk would change for the cases after it.
                tag = TagParser.parseCompoundFully(Args.string(input, "snbt")).copy();
            } catch (Exception e) {
                throw new CaseError("`snbt` isn't a compound: " + e.getMessage());
            }
        }
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        Lines lines = new Lines();
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        ByteArrayOutputStream result = new ByteArrayOutputStream();
        DataOutputStream after = new DataOutputStream(result);
        try {
            switch (op) {
                case "entities_load" -> loadEntities(pos, tag, after);
                case "entities_save" -> {
                    if (tag == null) {
                        throw new CaseError("`entities_save` takes `snbt`");
                    }
                    saveEntities(pos, tag, after);
                }
                case "poi" -> {
                    int minY = Args.asInt(Args.field(input, "min_y"), "`min_y`");
                    int sections = Args.asInt(Args.field(input, "sections"), "`sections`");
                    if ((minY & 15) != 0 || minY < -2032 || sections < 1 || minY + sections * 16 > 2032) {
                        throw new CaseError("`min_y` must be a multiple of 16 and the sections inside -2032 to 2032");
                    }
                    poi(pos, tag, LevelHeightAccessor.create(minY, sections * 16), after);
                }
                default -> throw new CaseError("no operation `" + op + "`");
            }
        } finally {
            root.removeAppender(lines);
        }
        out.writeInt(lines.taken.size());
        for (LogEvent event : lines.taken) {
            out.writeByte(switch (event.getLevel().name()) {
                case "WARN" -> 1;
                case "ERROR" -> 2;
                default -> 0;
            });
            text(out, event.getMessage().getFormattedMessage());
        }
        after.flush();
        out.write(result.toByteArray());
        out.flush();
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    // `EntityStorage.loadEntities`, up to the entities: a byte, 0 for no chunk, or 1, then a byte
    // for what's reported to the server, 0 for nothing, 1 for a misplaced chunk, then where it
    // says it is, or 2 for a position that can't be read, then each compound in `Entities`.
    private static void loadEntities(ChunkPos pos, CompoundTag tag, DataOutputStream out) throws Exception {
        if (tag == null) {
            out.writeByte(0);
            return;
        }
        org.slf4j.Logger logger = entityLogger();
        int report = 0;
        ChunkPos stored = null;
        try {
            ChunkPos storedPos = tag.<ChunkPos>read("Position", ChunkPos.CODEC).orElseThrow();
            if (!Objects.equals(pos, storedPos)) {
                logger.error("Chunk file at {} is in the wrong location. (Expected {}, got {})", new Object[]{pos, pos, storedPos});
                report = 1;
                stored = storedPos;
            }
        } catch (Exception e) {
            logger.warn("Failed to parse chunk {} position info", pos, e);
            report = 2;
        }
        Path folder = Files.createTempDirectory("calcite-entities");
        List<CompoundTag> entities = new ArrayList<>();
        try (SimpleRegionStorage storage = new SimpleRegionStorage(new RegionStorageInfo("probe", Level.OVERWORLD, "entities"), folder, DataFixers.getDataFixer(), false, DataFixTypes.ENTITY_CHUNK)) {
            CompoundTag upgraded = storage.upgradeChunkTag(tag, -1);
            try (ProblemReporter.ScopedCollector reporter = new ProblemReporter.ScopedCollector(ChunkAccess.problemPath(pos), logger)) {
                ValueInput chunkRoot = TagValueInput.create(reporter, RegistriesProbe.access(), upgraded);
                ValueInput.ValueInputList list = chunkRoot.childrenListOrEmpty("Entities");
                list.stream().map(EntitiesPoiProbe::compound).forEach(entities::add);
            }
        } finally {
            remove(folder);
        }
        out.writeByte(1);
        out.writeByte(report);
        if (report == 1) {
            out.writeInt(stored.x());
            out.writeInt(stored.z());
        }
        out.writeInt(entities.size());
        for (CompoundTag entity : entities) {
            root(out, entity);
        }
    }

    // `EntityStorage.storeEntities`, given the tags the entities saved, as `Entities` in the
    // case's compound, which has none for a chunk with no entities: a byte, 0 for that, which
    // stores nothing, or 1, then the chunk's tag. A chunk whose entities all decline to be saved
    // still has its empty list stored.
    private static void saveEntities(ChunkPos pos, CompoundTag given, DataOutputStream out) throws IOException {
        if (!given.contains("Entities")) {
            out.writeByte(0);
            return;
        }
        ListTag entities = given.getListOrEmpty("Entities");
        CompoundTag chunkTag = NbtUtils.addCurrentDataVersion(new CompoundTag());
        chunkTag.put("Entities", entities);
        chunkTag.store("Position", ChunkPos.CODEC, pos);
        out.writeByte(1);
        root(out, chunkTag);
    }

    // The chunk read as `SectionStorage` reads it for `PoiManager`, or none, then written back:
    // its tag.
    private static void poi(ChunkPos pos, CompoundTag tag, LevelHeightAccessor height, DataOutputStream out) throws Exception {
        Path folder = Files.createTempDirectory("calcite-poi");
        Tag written;
        try (SimpleRegionStorage regions = new SimpleRegionStorage(new RegionStorageInfo("probe", Level.OVERWORLD, "poi"), folder, DataFixers.getDataFixer(), false, DataFixTypes.POI_CHUNK)) {
            RegistryAccess access = RegistriesProbe.access();
            SectionStorage<PoiSection, PoiSection.Packed> storage = new SectionStorage<>(
                regions, PoiSection.Packed.CODEC, PoiSection::pack, PoiSection.Packed::unpack, PoiSection::new, access, NO_REPORTS, height
            );
            RegistryOps<Tag> ops = access.createSerializationContext(NbtOps.INSTANCE);
            Class<?> packed = Class.forName("net.minecraft.world.level.chunk.storage.SectionStorage$PackedChunk");
            Object chunk = null;
            if (tag != null) {
                Method parse = packed.getDeclaredMethod("parse", Codec.class, DynamicOps.class, Tag.class, SimpleRegionStorage.class, LevelHeightAccessor.class);
                parse.setAccessible(true);
                chunk = call(parse, null, PoiSection.Packed.CODEC, ops, tag, regions, height);
            }
            Method unpack = SectionStorage.class.getDeclaredMethod("unpackChunk", ChunkPos.class, packed);
            unpack.setAccessible(true);
            call(unpack, storage, pos, chunk);
            Method write = SectionStorage.class.getDeclaredMethod("writeChunk", ChunkPos.class, DynamicOps.class);
            write.setAccessible(true);
            written = (Tag) ((Dynamic<?>) call(write, storage, pos, ops)).getValue();
        } finally {
            remove(folder);
        }
        if (!(written instanceof CompoundTag compound)) {
            throw new CaseError("writeChunk gave " + written);
        }
        root(out, compound);
    }

    private static Object call(Method method, Object on, Object... args) throws Exception {
        try {
            return method.invoke(on, args);
        } catch (InvocationTargetException e) {
            if (e.getCause() instanceof Exception cause) {
                throw cause;
            }
            throw e;
        }
    }

    // The compound a list's element was read from.
    private static CompoundTag compound(ValueInput input) {
        if (!(input instanceof TagValueInput)) {
            return new CompoundTag();
        }
        try {
            Field field = TagValueInput.class.getDeclaredField("input");
            field.setAccessible(true);
            return (CompoundTag) field.get(input);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(e);
        }
    }

    private static org.slf4j.Logger entityLogger() throws ReflectiveOperationException {
        Field field = EntityStorage.class.getDeclaredField("LOGGER");
        field.setAccessible(true);
        return (org.slf4j.Logger) field.get(null);
    }

    // An `int` length, then the compound as `NbtIo.write` writes a file's root.
    private static void root(DataOutputStream out, CompoundTag tag) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        NbtIo.write(tag, new DataOutputStream(bytes));
        out.writeInt(bytes.size());
        out.write(bytes.toByteArray());
    }

    private static void remove(Path folder) throws IOException {
        try (Stream<Path> paths = Files.walk(folder)) {
            for (Path p : paths.sorted(Comparator.reverseOrder()).toList()) {
                Files.delete(p);
            }
        }
    }

    private static void text(DataOutputStream out, String text) throws IOException {
        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(utf8.length);
        out.write(utf8);
    }

    /** What vanilla logs while the chunk is read and written. */
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();

        Lines() {
            super("entities-poi-probe", null, null, true, Property.EMPTY_ARRAY);
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }
    }
}
