package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.ParseResults;
import com.mojang.brigadier.context.CommandContextBuilder;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.context.ParsedArgument;
import com.mojang.brigadier.context.ParsedCommandNode;
import com.mojang.brigadier.context.StringRange;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import java.util.List;
import java.util.Map;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.HolderLookup;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.network.chat.ComponentUtils;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.server.permissions.PermissionLevel;

/**
 * `command_parse`: a command read as a dedicated server's {@code CommandDispatcher.parse} reads it,
 * for a source of a permission level, and the error {@code Commands.finishParsing} fails it with
 * (CAL-367).
 */
final class CommandParseProbe implements Probe {
    private HolderLookup.Provider registries;
    private CommandDispatcher<CommandSourceStack> dispatcher;

    @Override
    public String name() {
        return "command_parse";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (dispatcher == null) {
            registries = VanillaRegistries.createWorldLookup();
            dispatcher = new Commands(Commands.CommandSelection.DEDICATED, Commands.createValidationContext(registries)).getDispatcher();
        }
        String text = Args.string(input, "input");
        int level = Args.asInt(Args.field(input, "level"), "level");
        if (level < 0 || level > 4) {
            throw new CaseError("`level` must be 0 to 4");
        }
        CommandSourceStack source = Commands.createCompilationContext(LevelBasedPermissionSet.forLevel(PermissionLevel.byId(level)));
        ParseResults<CommandSourceStack> parse = dispatcher.parse(text, source);

        JsonArray contexts = new JsonArray();
        for (CommandContextBuilder<CommandSourceStack> c = parse.getContext(); c != null; c = c.getChild()) {
            JsonObject context = new JsonObject();
            JsonArray nodes = new JsonArray();
            for (ParsedCommandNode<CommandSourceStack> node : c.getNodes()) {
                nodes.add(read(node.getNode().getName(), node.getRange()));
            }
            JsonArray arguments = new JsonArray();
            for (Map.Entry<String, ParsedArgument<CommandSourceStack, ?>> argument : c.getArguments().entrySet()) {
                arguments.add(read(argument.getKey(), argument.getValue().getRange()));
            }
            context.add("nodes", nodes);
            context.add("arguments", arguments);
            context.addProperty("command", c.getCommand() != null);
            contexts.add(context);
        }
        JsonObject output = new JsonObject();
        output.add("contexts", contexts);
        output.addProperty("cursor", parse.getReader().getCursor());

        // As `Commands.finishParsing` fails it: `validateParseResults`, then a last context with
        // no command, `ContextChain.tryFlatten`.
        CommandSyntaxException error = Commands.getParseException(parse);
        if (error == null && ContextChain.tryFlatten(parse.getContext().build(text)).isEmpty()) {
            error = CommandSyntaxException.BUILT_IN_EXCEPTIONS.dispatcherUnknownCommand().createWithContext(parse.getReader());
        }
        if (error == null) {
            output.add("error", JsonNull.INSTANCE);
            return Result.ok(output);
        }
        JsonObject failed = new JsonObject();
        failed.addProperty("cursor", error.getCursor());
        output.add("error", failed);
        Tag message = ComponentSerialization.CODEC
                .encodeStart(registries.createSerializationContext(NbtOps.INSTANCE), ComponentUtils.fromMessage(error.getRawMessage()))
                .getOrThrow();
        return Result.ok(output, NbtProbe.binary(message));
    }

    private static JsonArray read(String name, StringRange range) {
        JsonArray out = new JsonArray();
        out.add(name);
        out.add(range.getStart());
        out.add(range.getEnd());
        return out;
    }
}
