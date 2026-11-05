package calcite.rig.vanilla;

import com.google.common.hash.HashCode;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.DynamicOps;
import com.mojang.serialization.JsonOps;
import io.netty.buffer.Unpooled;
import java.io.IOException;
import java.util.List;
import java.util.TreeMap;
import java.util.TreeSet;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.component.DataComponentPatch;
import net.minecraft.core.component.DataComponentType;
import net.minecraft.core.component.TypedDataComponent;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.nbt.TagParser;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.util.HashOps;
import net.minecraft.world.item.ItemStack;

/**
 * `items`: an item stack read as vanilla reads one, from a data pack's JSON or a save's NBT with
 * `ItemStack.CODEC`, or from the network with `ItemStack.OPTIONAL_STREAM_CODEC`, then written to
 * NBT with the codec or to the network with the stream codec, or hashed as a slot's
 * `HashedStack` is. The registries are the vanilla data pack's, with the items' default
 * components bound, as a server has them.
 */
final class ItemsProbe implements Probe {
    private static final TagParser<Tag> SNBT = TagParser.create(NbtOps.INSTANCE);

    @Override
    public String name() {
        return "items";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        RegistryAccess.Frozen access = RegistriesProbe.access();
        String from = Args.string(input, "from");
        String to = Args.string(input, "to");
        JsonObject output = new JsonObject();
        ItemStack stack;
        switch (from) {
            case "json", "snbt" -> {
                DataResult<ItemStack> read;
                if (from.equals("json")) {
                    JsonElement element;
                    try {
                        element = JsonParser.parseString(Args.string(input, "value"));
                    } catch (JsonParseException e) {
                        throw new CaseError("`value` isn't JSON: " + e.getMessage());
                    }
                    read = ItemStack.CODEC.parse(access.createSerializationContext(JsonOps.INSTANCE), element);
                } else {
                    Tag tag;
                    try {
                        tag = SNBT.parseFully(Args.string(input, "value"));
                    } catch (Exception e) {
                        throw new CaseError("`value` isn't SNBT: " + e.getMessage());
                    }
                    read = ItemStack.CODEC.parse(access.createSerializationContext(NbtOps.INSTANCE), tag);
                }
                if (read.isError()) {
                    output.addProperty("error", read.error().orElseThrow().message());
                    output.addProperty("partial", read.hasResultOrPartial());
                    return Result.ok(output);
                }
                stack = read.getOrThrow();
            }
            case "wire" -> {
                RegistryFriendlyByteBuf buf = new RegistryFriendlyByteBuf(Unpooled.wrappedBuffer(Args.oneBlob(blobs)), access);
                try {
                    stack = ItemStack.OPTIONAL_STREAM_CODEC.decode(buf);
                } catch (RuntimeException e) {
                    output.addProperty("error", e.toString());
                    return Result.ok(output);
                }
                if (buf.readableBytes() != 0) {
                    output.addProperty("left", buf.readableBytes());
                }
            }
            default -> throw new CaseError("`from` must be `json`, `snbt` or `wire`, not `" + from + "`");
        }
        output.addProperty("empty", stack.isEmpty());
        switch (to) {
            case "nbt" -> {
                if (stack.isEmpty()) {
                    return Result.ok(output);
                }
                DataResult<Tag> written = ItemStack.CODEC.encodeStart(access.createSerializationContext(NbtOps.INSTANCE), stack);
                if (written.isError()) {
                    output.addProperty("write_error", written.error().orElseThrow().message());
                    return Result.ok(output);
                }
                return Result.ok(output, NbtProbe.binary(written.getOrThrow()));
            }
            case "wire" -> {
                RegistryFriendlyByteBuf buf = new RegistryFriendlyByteBuf(Unpooled.buffer(), access);
                try {
                    ItemStack.OPTIONAL_STREAM_CODEC.encode(buf, stack);
                } catch (RuntimeException e) {
                    output.addProperty("write_error", e.toString());
                    return Result.ok(output);
                }
                byte[] bytes = new byte[buf.readableBytes()];
                buf.readBytes(bytes);
                return Result.ok(output, bytes);
            }
            case "hash" -> {
                if (stack.isEmpty()) {
                    return Result.ok(output);
                }
                output.add("hash", hashed(access, stack));
                return Result.ok(output);
            }
            default -> throw new CaseError("`to` must be `nbt`, `wire` or `hash`, not `" + to + "`");
        }
    }

    /**
     * The stack as a slot's `HashedStack` has it: its item, its count, and each component its
     * patch sets, by its type's ID in order, with its value hashed as `ServerPlayer`'s container
     * synchronizer hashes it, written with its codec to `HashOps.CRC32C_INSTANCE` through the
     * registries, and each type the patch takes away, in order (CAL-136).
     */
    private static JsonObject hashed(RegistryAccess.Frozen access, ItemStack stack) {
        DynamicOps<HashCode> ops = access.createSerializationContext(HashOps.CRC32C_INSTANCE);
        DataComponentPatch.SplitResult split = stack.getComponentsPatch().split();
        TreeMap<String, JsonPrimitive> added = new TreeMap<>();
        for (TypedDataComponent<?> component : split.added()) {
            String key = BuiltInRegistries.DATA_COMPONENT_TYPE.getKey(component.type()).toString();
            DataResult<HashCode> result = component.encodeValue(ops);
            added.put(key, result.isError()
                ? new JsonPrimitive("error: " + result.error().orElseThrow().message())
                : new JsonPrimitive(result.getOrThrow().asInt()));
        }
        TreeSet<String> removed = new TreeSet<>();
        for (DataComponentType<?> type : split.removed()) {
            removed.add(BuiltInRegistries.DATA_COMPONENT_TYPE.getKey(type).toString());
        }
        JsonObject hash = new JsonObject();
        hash.addProperty("item", BuiltInRegistries.ITEM.getKey(stack.getItem()).toString());
        hash.addProperty("count", stack.getCount());
        JsonObject addedJson = new JsonObject();
        added.forEach(addedJson::add);
        hash.add("added", addedJson);
        JsonArray removedJson = new JsonArray();
        removed.forEach(removedJson::add);
        hash.add("removed", removedJson);
        return hash;
    }
}
