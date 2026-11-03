package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.List;
import net.minecraft.SharedConstants;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.TagParser;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.util.datafix.DataFixers;

/**
 * `datafix`: data saved by an older game, upgraded by vanilla's data fixers to 26.3's, as a
 * structure template is when it loads (`TemplateSource.readStructure`): from its `DataVersion`,
 * 500 if it hasn't one, unless the case gives `version`. The data is SNBT, or a gzipped NBT file
 * as a blob, and the output is the upgraded data as SNBT.
 */
final class DatafixProbe implements Probe {
    @Override
    public String name() {
        return "datafix";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        String type = Args.string(input, "type");
        DataFixTypes fixType = switch (type) {
            case "structure" -> DataFixTypes.STRUCTURE;
            default -> throw new CaseError("unknown `type`: `" + type + "`");
        };
        CompoundTag tag;
        if (input.has("snbt")) {
            try {
                tag = TagParser.parseCompoundFully(Args.string(input, "snbt"));
            } catch (Exception e) {
                throw new CaseError("`snbt` doesn't parse: " + e.getMessage());
            }
        } else {
            tag = NbtIo.readCompressed(new ByteArrayInputStream(Args.oneBlob(blobs)), NbtAccounter.unlimitedHeap());
        }
        int from = input.has("version") ? (int) Args.int64(input, "version") : NbtUtils.getDataVersion(tag, 500);
        int to = SharedConstants.getCurrentVersion().dataVersion().version();
        JsonObject output = new JsonObject();
        CompoundTag fixed;
        try {
            fixed = fixType.update(DataFixers.getDataFixer(), tag, from, to);
        } catch (RuntimeException e) {
            // `TemplateSource.load` logs what reading a template throws, and has no template.
            output.addProperty("loads", false);
            return Result.ok(output);
        }
        output.addProperty("snbt", fixed.toString());
        return Result.ok(output);
    }
}
