package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.List;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.nbt.TagParser;

/** `nbt`: parses SNBT or binary NBT, then prints it as SNBT and writes it back as binary. */
final class NbtProbe implements Probe {
    private static final TagParser<Tag> ANY = TagParser.create(NbtOps.INSTANCE);

    @Override
    public String name() {
        return "nbt";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        String from = Args.string(input, "from");
        Tag tag;
        try {
            tag = switch (from) {
                case "snbt" -> TagParser.parseCompoundFully(Args.string(input, "snbt"));
                case "snbt_any" -> ANY.parseFully(Args.string(input, "snbt"));
                case "binary" -> {
                    byte[] blob = Args.oneBlob(blobs);
                    yield NbtIo.readAnyTag(new DataInputStream(new ByteArrayInputStream(blob)), NbtAccounter.unlimitedHeap());
                }
                default -> throw new CaseError("unknown `from`: `" + from + "`");
            };
        } catch (CaseError e) {
            throw e;
        } catch (Exception e) {
            return Result.rejected(e);
        }
        return Result.ok(describe(tag), binary(tag));
    }

    static JsonObject describe(Tag tag) {
        JsonObject output = new JsonObject();
        output.addProperty("snbt", tag.toString());
        output.addProperty("type", tag.getId());
        return output;
    }

    static byte[] binary(Tag tag) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        NbtIo.writeAnyTag(tag, new DataOutputStream(bytes));
        return bytes.toByteArray();
    }
}
