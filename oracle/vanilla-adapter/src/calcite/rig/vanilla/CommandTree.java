package calcite.rig.vanilla;

import com.mojang.brigadier.tree.ArgumentCommandNode;
import com.mojang.brigadier.tree.CommandNode;
import com.mojang.brigadier.tree.LiteralCommandNode;
import com.mojang.brigadier.tree.RootCommandNode;
import io.netty.buffer.Unpooled;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.SharedConstants;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.synchronization.ArgumentTypeInfo;
import net.minecraft.commands.synchronization.ArgumentTypeInfos;
import net.minecraft.commands.synchronization.SuggestionProviders;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.Bootstrap;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.server.permissions.PermissionLevel;

/**
 * Writes the dedicated server's command tree to the JSON file named by its argument, read by
 * oracle/datagen/calx_tables.calx for src/command/tree.calx. Run by
 * oracle/datagen/command_tree.calx (CAL-165).
 *
 * <p>The data generator's {@code commands.json} sorts each node's children by name, but the
 * {@code commands} packet numbers the nodes breadth first in the order they were registered,
 * which {@code CommandDispatcher} keeps, so this walks vanilla's own {@code Commands} as a
 * dedicated server builds it. Each node, in that walk's order from the root: its kind, its name,
 * its children by their places in the list, whether it's executable, the node it redirects to,
 * the lowest permission level whose source may use it, {@code canUse}, and for an argument, its
 * argument type's ID in {@code command_argument_type} and name, its properties as the packet
 * writes them, {@code serializeToNetwork}, in hex, and its custom suggestions' name, where it has
 * them.
 */
final class CommandTree {
    private CommandTree() {}

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: CommandTree <out.json>");
        }
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        Commands commands = new Commands(Commands.CommandSelection.DEDICATED,
                Commands.createValidationContext(VanillaRegistries.createWorldLookup()));
        RootCommandNode<CommandSourceStack> root = commands.getDispatcher().getRoot();
        List<CommandNode<CommandSourceStack>> nodes = new ArrayList<>();
        Map<CommandNode<CommandSourceStack>, Integer> ids = new IdentityHashMap<>();
        walk(root, nodes, ids);
        List<CommandSourceStack> sources = new ArrayList<>();
        for (int level = 0; level <= 4; level++) {
            sources.add(Commands.createCompilationContext(LevelBasedPermissionSet.forLevel(PermissionLevel.byId(level))));
        }
        StringBuilder json = new StringBuilder();
        json.append("{\n  \"game_version\": \"").append(SharedConstants.getCurrentVersion().name()).append("\",\n");
        json.append("  \"nodes\": [\n");
        for (int i = 0; i < nodes.size(); i++) {
            CommandNode<CommandSourceStack> node = nodes.get(i);
            json.append("    {\"kind\": \"");
            if (node instanceof RootCommandNode) {
                json.append("root\"");
            } else if (node instanceof LiteralCommandNode<CommandSourceStack> literal) {
                json.append("literal\", \"name\": ").append(quote(literal.getLiteral()));
            } else {
                json.append("argument\", \"name\": ").append(quote(node.getName()));
            }
            json.append(", \"children\": [");
            boolean first = true;
            for (CommandNode<CommandSourceStack> child : node.getChildren()) {
                if (!first) {
                    json.append(", ");
                }
                first = false;
                json.append(ids.get(child));
            }
            json.append("], \"executable\": ").append(node.getCommand() != null);
            json.append(", \"redirect\": ").append(node.getRedirect() == null ? -1 : ids.get(node.getRedirect()));
            int level = 5;
            for (int l = 0; l <= 4; l++) {
                if (node.canUse(sources.get(l))) {
                    level = l;
                    break;
                }
            }
            json.append(", \"level\": ").append(level);
            if (node instanceof ArgumentCommandNode<CommandSourceStack, ?> argument) {
                ArgumentTypeInfo.Template<?> template = ArgumentTypeInfos.unpack(argument.getType());
                ArgumentTypeInfo<?, ?> info = template.type();
                json.append(", \"parser\": ").append(BuiltInRegistries.COMMAND_ARGUMENT_TYPE.getId(info));
                json.append(", \"parser_name\": ").append(quote(BuiltInRegistries.COMMAND_ARGUMENT_TYPE.getKey(info).toString()));
                json.append(", \"properties\": ").append(quote(properties(template)));
                if (argument.getCustomSuggestions() != null) {
                    json.append(", \"suggestions\": ").append(quote(SuggestionProviders.getName(argument.getCustomSuggestions()).toString()));
                }
            }
            json.append("}").append(i + 1 < nodes.size() ? ",\n" : "\n");
        }
        json.append("  ]\n}\n");
        Files.writeString(Path.of(args[0]), json, StandardCharsets.UTF_8);
    }

    // Each node from `node` down, in the order brigadier keeps its children, numbered as it's
    // first come to.
    private static void walk(CommandNode<CommandSourceStack> node, List<CommandNode<CommandSourceStack>> nodes,
            Map<CommandNode<CommandSourceStack>, Integer> ids) {
        if (ids.containsKey(node)) {
            return;
        }
        ids.put(node, nodes.size());
        nodes.add(node);
        for (CommandNode<CommandSourceStack> child : node.getChildren()) {
            walk(child, nodes, ids);
        }
    }

    @SuppressWarnings("unchecked")
    private static <A extends com.mojang.brigadier.arguments.ArgumentType<?>, T extends ArgumentTypeInfo.Template<A>> String properties(
            ArgumentTypeInfo.Template<A> template) {
        FriendlyByteBuf buf = new FriendlyByteBuf(Unpooled.buffer());
        ArgumentTypeInfo<A, T> info = (ArgumentTypeInfo<A, T>) template.type();
        info.serializeToNetwork((T) template, buf);
        byte[] bytes = new byte[buf.readableBytes()];
        buf.readBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }

    private static String quote(String s) {
        StringBuilder out = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') {
                out.append('\\');
            }
            out.append(c);
        }
        return out.append('"').toString();
    }
}
