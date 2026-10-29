package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import com.mojang.serialization.Dynamic;
import com.mojang.serialization.Lifecycle;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.TagParser;
import net.minecraft.world.level.LevelSettings;
import net.minecraft.world.level.WorldDataConfiguration;
import net.minecraft.world.level.storage.LevelStorageSource;
import net.minecraft.world.level.storage.PrimaryLevelData;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `level_data`: the `Data` compound of a `level.dat`, given as SNBT, read as a server reads it as
 * it starts, by `LevelStorageSource.readDataConfig`, `LevelSettings.parse` and
 * `PrimaryLevelData.parse`, then written back by `createTag`, as `saveDataTag` writes it. The blob
 * is what was logged, then the NBT written, with `LastPlayed`, the clock's, as 0.
 */
final class LevelDataProbe implements Probe {
    @Override
    public String name() {
        return "level_data";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        if (!blobs.isEmpty()) {
            throw new CaseError("`level_data` takes no blobs");
        }
        CompoundTag tag;
        try {
            tag = TagParser.parseCompoundFully(Args.string(input, "snbt"));
        } catch (Exception e) {
            throw new CaseError("`snbt` isn't a compound: " + e.getMessage());
        }
        Lines lines = new Lines();
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        CompoundTag written;
        try {
            Dynamic<?> data = new Dynamic<>(NbtOps.INSTANCE, tag);
            WorldDataConfiguration config = LevelStorageSource.readDataConfig(data);
            LevelSettings settings = LevelSettings.parse(data, config);
            PrimaryLevelData level = PrimaryLevelData.parse(data, settings, PrimaryLevelData.SpecialWorldProperty.NONE, Lifecycle.stable());
            written = level.createTag(null);
        } finally {
            root.removeAppender(lines);
        }
        if (written.contains("LastPlayed")) {
            written.putLong("LastPlayed", 0L);
        }
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        out.writeInt(lines.taken.size());
        for (LogEvent event : lines.taken) {
            out.writeByte(switch (event.getLevel().name()) {
                case "WARN" -> 1;
                case "ERROR" -> 2;
                default -> 0;
            });
            text(out, event.getMessage().getFormattedMessage());
        }
        ByteArrayOutputStream nbt = new ByteArrayOutputStream();
        NbtIo.write(written, new DataOutputStream(nbt));
        out.writeInt(nbt.size());
        out.write(nbt.toByteArray());
        out.flush();
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    private static void text(DataOutputStream out, String text) throws IOException {
        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(utf8.length);
        out.write(utf8);
    }

    /** What vanilla logs while the level's data is read and written. */
    private static final class Lines extends AbstractAppender {
        final List<LogEvent> taken = new ArrayList<>();

        Lines() {
            super("level-data-probe", null, null, true, Property.EMPTY_ARRAY);
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }
    }
}
