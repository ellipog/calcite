package calcite.rig.vanilla;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.DynamicOps;
import com.mojang.serialization.JsonOps;
import java.io.IOException;
import java.util.List;
import net.minecraft.core.HolderLookup;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.nbt.TagParser;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.util.GsonHelper;

/** `text`: decodes a text component, then encodes it back as JSON and as NBT. */
final class TextProbe implements Probe {
    private static final TagParser<Tag> SNBT = TagParser.create(NbtOps.INSTANCE);

    /** Vanilla's built-in registries, so hover events can show items and entities. Built on first use. */
    private HolderLookup.Provider registries;

    @Override
    public String name() {
        return "text";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        if (registries == null) {
            registries = VanillaRegistries.createWorldLookup();
        }
        DynamicOps<JsonElement> json = registries.createSerializationContext(JsonOps.INSTANCE);
        DynamicOps<Tag> nbt = registries.createSerializationContext(NbtOps.INSTANCE);

        DataResult<Component> decoded;
        if (input.has("json")) {
            JsonElement element;
            try {
                element = JsonParser.parseString(Args.string(input, "json"));
            } catch (JsonParseException e) {
                return Result.rejected(e);
            }
            decoded = ComponentSerialization.CODEC.parse(json, element);
        } else if (input.has("snbt")) {
            Tag tag;
            try {
                tag = SNBT.parseFully(Args.string(input, "snbt"));
            } catch (CommandSyntaxException e) {
                return Result.rejected(e);
            }
            decoded = ComponentSerialization.CODEC.parse(nbt, tag);
        } else {
            throw new CaseError("needs `json` or `snbt`");
        }
        if (decoded.isError()) {
            JsonObject output = new JsonObject();
            output.addProperty("error", decoded.error().orElseThrow().message());
            return Result.ok(output);
        }
        Component component = decoded.getOrThrow();

        JsonObject output = new JsonObject();
        output.addProperty("json", GsonHelper.toStableString(ComponentSerialization.CODEC.encodeStart(json, component).getOrThrow()));
        output.addProperty("plain", component.getString());
        Tag tag = ComponentSerialization.CODEC.encodeStart(nbt, component).getOrThrow();
        return Result.ok(output, NbtProbe.binary(tag));
    }
}
