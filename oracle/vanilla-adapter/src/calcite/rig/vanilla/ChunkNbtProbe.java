package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.TagParser;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.storage.SerializableChunkData;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

/**
 * `chunk_nbt`: a chunk's NBT, given as SNBT, read by vanilla's {@link SerializableChunkData#parse}
 * for a world `min_y` up with `sections` sections, then written back by its `write`, as a chunk is
 * read from its region file and saved again. The blob is what was logged, then the NBT written, or
 * nothing if there's no chunk, or what was thrown.
 */
final class ChunkNbtProbe implements Probe {
    private static PalettedContainerFactory containers;

    @Override
    public String name() {
        return "chunk_nbt";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        if (!blobs.isEmpty()) {
            throw new CaseError("`chunk_nbt` takes no blobs");
        }
        int minY = Args.asInt(Args.field(input, "min_y"), "`min_y`");
        int sections = Args.asInt(Args.field(input, "sections"), "`sections`");
        if ((minY & 15) != 0 || minY < -2032 || sections < 1 || minY + sections * 16 > 2032) {
            throw new CaseError("`min_y` must be a multiple of 16 and the sections inside -2032 to 2032");
        }
        CompoundTag tag;
        try {
            tag = TagParser.parseCompoundFully(Args.string(input, "snbt"));
        } catch (Exception e) {
            throw new CaseError("`snbt` isn't a compound: " + e.getMessage());
        }
        if (containers == null) {
            containers = PalettedContainerFactory.create(RegistriesProbe.access());
        }
        Lines lines = new Lines();
        Logger root = (Logger) LogManager.getRootLogger();
        root.addAppender(lines);
        byte outcome;
        byte[] written = new byte[0];
        String thrown = null;
        String message = null;
        try {
            SerializableChunkData data = SerializableChunkData.parse(LevelHeightAccessor.create(minY, sections * 16), containers, tag);
            if (data == null) {
                outcome = 0;
            } else {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                NbtIo.write(data.write(), new DataOutputStream(bytes));
                written = bytes.toByteArray();
                outcome = 1;
            }
        } catch (RuntimeException e) {
            outcome = 2;
            thrown = e.getClass().getSimpleName();
            message = e.getMessage() == null ? "" : e.getMessage();
        } finally {
            root.removeAppender(lines);
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
        out.writeByte(outcome);
        if (outcome == 1) {
            out.writeInt(written.length);
            out.write(written);
        } else if (outcome == 2) {
            text(out, thrown);
            text(out, message);
        }
        out.flush();
        return Result.ok(new JsonObject(), bytes.toByteArray());
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
            super("chunk-nbt-probe", null, null, true, Property.EMPTY_ARRAY);
            start();
        }

        @Override
        public void append(LogEvent event) {
            taken.add(event.toImmutable());
        }
    }
}
