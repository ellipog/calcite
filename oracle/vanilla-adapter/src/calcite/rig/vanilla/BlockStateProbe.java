package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.brigadier.StringReader;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.TagParser;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;

/**
 * `block_state`: global block state IDs to states and back, the block registry's state layout, the
 * command parser's block state syntax, and the NBT form chunks and structures store states in.
 */
final class BlockStateProbe implements Probe {
    @Override
    public String name() {
        return "block_state";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        String op = Args.string(input, "op");
        return switch (op) {
            case "by_id" -> byId(Args.asInt(Args.field(input, "from"), "`from`"), count(input));
            case "blocks" -> blocks(Args.asInt(Args.field(input, "from"), "`from`"), count(input));
            case "parse" -> parse(Args.string(input, "input"), bool(input, "nbt"));
            case "from_nbt" -> fromNbt(Args.string(input, "snbt"));
            default -> throw new CaseError("unknown `op`: `" + op + "`");
        };
    }

    private static int count(JsonObject input) {
        int count = Args.asInt(Args.field(input, "count"), "`count`");
        if (count < 0 || count > 4096) {
            throw new CaseError("`count` must be 0 to 4096");
        }
        return count;
    }

    private static boolean bool(JsonObject input, String name) {
        var value = Args.field(input, name);
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("`" + name + "` must be a boolean");
        }
        return value.getAsBoolean();
    }

    /**
     * Each ID's state as the command syntax prints it, or null where the ID map has no state (the
     * game reads those as air). Every state is also printed and parsed back, and written to NBT and
     * read back; any ID that doesn't come back to itself is listed.
     */
    private static Result byId(int from, int count) {
        JsonArray states = new JsonArray();
        JsonArray defaults = new JsonArray();
        JsonArray mismatches = new JsonArray();
        for (long i = from; i < (long) from + count; i++) {
            int id = (int) i;
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            if (state == null) {
                states.add((String) null);
                continue;
            }
            String text = BlockStateParser.serialize(state);
            states.add(text);
            if (state == state.getBlock().defaultBlockState()) {
                defaults.add(id);
            }
            int parsed;
            try {
                parsed = Block.getId(BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK, text, false).blockState());
            } catch (CommandSyntaxException e) {
                parsed = -1;
            }
            int read = Block.getId(NbtUtils.readBlockState(BuiltInRegistries.BLOCK, NbtUtils.writeBlockState(state)));
            if (parsed != id || read != id) {
                mismatches.add(id);
            }
        }
        JsonObject output = new JsonObject();
        output.add("states", states);
        output.add("defaults", defaults);
        output.add("round_trip_mismatches", mismatches);
        return Result.ok(output);
    }

    /** Each block's state layout: its first state ID, state count, default state and properties. */
    private static Result blocks(int from, int count) {
        JsonArray blocks = new JsonArray();
        for (long i = from; i < (long) from + count; i++) {
            var holder = BuiltInRegistries.BLOCK.get((int) i);
            if (holder.isEmpty()) {
                blocks.add((JsonObject) null);
                continue;
            }
            Block block = holder.get().value();
            List<BlockState> possible = block.getStateDefinition().getPossibleStates();
            JsonObject entry = new JsonObject();
            entry.addProperty("name", holder.get().key().identifier().toString());
            entry.addProperty("first_state", Block.getId(possible.get(0)));
            entry.addProperty("state_count", possible.size());
            entry.addProperty("default_state", Block.getId(block.defaultBlockState()));
            JsonArray properties = new JsonArray();
            for (Property<?> property : block.getStateDefinition().getProperties()) {
                properties.add(property(property));
            }
            entry.add("properties", properties);
            blocks.add(entry);
        }
        JsonObject output = new JsonObject();
        output.add("blocks", blocks);
        return Result.ok(output);
    }

    private static <T extends Comparable<T>> JsonObject property(Property<T> property) {
        JsonObject out = new JsonObject();
        out.addProperty("name", property.getName());
        JsonArray values = new JsonArray();
        for (T value : property.getPossibleValues()) {
            values.add(property.getName(value));
        }
        out.add("values", values);
        return out;
    }

    /** The command syntax, as `/setblock` reads it: `name[property=value,...]{nbt}`. */
    private static Result parse(String text, boolean allowNbt) {
        StringReader reader = new StringReader(text);
        BlockStateParser.BlockResult result;
        try {
            result = BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK, reader, allowNbt);
        } catch (CommandSyntaxException e) {
            return Result.rejected(e);
        }
        JsonObject output = state(result.blockState());
        // The properties the input named, as opposed to the ones left at the block's defaults.
        Map<String, String> given = new TreeMap<>();
        for (Map.Entry<Property<?>, Comparable<?>> e : result.properties().entrySet()) {
            given.put(e.getKey().getName(), valueName(e.getKey(), e.getValue()));
        }
        JsonObject properties = new JsonObject();
        given.forEach(properties::addProperty);
        output.add("given", properties);
        output.addProperty("nbt", result.nbt() == null ? null : result.nbt().toString());
        output.addProperty("cursor", reader.getCursor());
        return Result.ok(output);
    }

    /** The NBT form, as chunks and structure templates store it: `{id: name, properties: {...}}`. */
    private static Result fromNbt(String snbt) {
        CompoundTag tag;
        try {
            tag = TagParser.parseCompoundFully(snbt);
        } catch (CommandSyntaxException e) {
            throw new CaseError("bad SNBT in the case: " + e.getMessage());
        }
        return Result.ok(state(NbtUtils.readBlockState(BuiltInRegistries.BLOCK, tag)));
    }

    private static JsonObject state(BlockState state) {
        JsonObject out = new JsonObject();
        out.addProperty("id", Block.getId(state));
        out.addProperty("state", BlockStateParser.serialize(state));
        out.addProperty("written", NbtUtils.writeBlockState(state).toString());
        return out;
    }

    @SuppressWarnings("unchecked")
    private static <T extends Comparable<T>> String valueName(Property<T> property, Comparable<?> value) {
        return property.getName((T) value);
    }
}
