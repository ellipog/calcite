package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.ByteBufUtil;
import io.netty.buffer.Unpooled;
import java.io.DataInputStream;
import java.io.EOFException;
import java.io.IOException;
import java.io.Writer;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.lang.reflect.RecordComponent;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.BitSet;
import java.util.Collection;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.OptionalDouble;
import java.util.OptionalInt;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import net.minecraft.SharedConstants;
import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.Packet;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.item.ItemStack;

/**
 * Reads the sessions the rig's protocol bot recorded (P4.8) with vanilla's own codecs, and writes
 * each packet out as a tree of plain values, so `rig/runner/sessions.py` can compare what vanilla
 * and Calcite sent field by field.
 *
 * <p>A session holds records one after another, as `src/rig/session.calx` writes them: the
 * state's number, the length as 4 bytes, big-endian, then the packet's ID and fields. A record of
 * state 255 is the bot's mark, whose bytes are text. For each `X.bin` this writes `X.jsonl`, one
 * JSON object a line: `{"mark": text}` for a mark, and for a packet its state, its kind, its
 * length, a SHA-256 of its bytes, and `value`, the packet as a tree. A packet that doesn't decode,
 * or leaves bytes over, has `error` instead.
 *
 * <p>The tree is a record's components or an object's fields by name, with the type's simple
 * name under `@`; lists as arrays, sets and maps sorted, since their order isn't the packet's;
 * registry entries by name, and so is anything a built-in registry holds, such as an argument
 * type; components and SNBT values as vanilla prints them; functions by their type; and byte
 * arrays over 64 bytes as their length and a hash. A packet's tree stops at a million values.
 *
 * <pre>java -cp ... calcite.rig.vanilla.SessionDump build/rig/sessions/.../join.bin</pre>
 */
public final class SessionDump {
    private SessionDump() {}

    // Everything the built-in registries hold, by identity, with its registry's name and its own.
    private static final IdentityHashMap<Object, String> REGISTERED = new IdentityHashMap<>();
    private static final int BUDGET = 1_000_000;
    private static int left;

    public static void main(String[] args) throws IOException {
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        for (Registry<?> r : BuiltInRegistries.REGISTRY) {
            String registry = r.key().identifier().toString();
            for (var e : r.entrySet()) {
                REGISTERED.putIfAbsent(e.getValue(), "#" + registry + "/" + e.getKey().identifier());
            }
        }
        for (String file : args) {
            Path in = Path.of(file);
            String name = in.getFileName().toString().replaceFirst("\\.bin$", "");
            Path out = in.resolveSibling(name + ".jsonl");
            try (DataInputStream data = new DataInputStream(Files.newInputStream(in));
                 Writer w = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
                while (true) {
                    int state;
                    try {
                        state = data.readUnsignedByte();
                    } catch (EOFException e) {
                        break;
                    }
                    byte[] bytes = new byte[data.readInt()];
                    data.readFully(bytes);
                    JsonObject line = new JsonObject();
                    if (state == 255) {
                        line.addProperty("mark", new String(bytes, StandardCharsets.UTF_8));
                    } else {
                        dump(state, bytes, line);
                    }
                    w.write(line.toString());
                    w.write('\n');
                }
            }
        }
    }

    private static void dump(int state, byte[] bytes, JsonObject line) {
        line.addProperty("state", stateName(state));
        line.addProperty("size", bytes.length);
        line.addProperty("sha256", sha256(bytes));
        StreamCodec<ByteBuf, Packet<?>> codec = PacketCheck.codecOf(state);
        ByteBuf in = Unpooled.wrappedBuffer(bytes);
        Packet<?> packet;
        try {
            packet = codec.decode(in);
        } catch (RuntimeException e) {
            line.addProperty("kind", "id " + PacketCheck.idOf(bytes));
            line.addProperty("error", "doesn't decode: " + e + " " + ByteBufUtil.hexDump(bytes, 0, Math.min(bytes.length, 64)));
            return;
        }
        line.addProperty("kind", packet.type().id().getPath());
        if (in.readableBytes() > 0) {
            line.addProperty("error", in.readableBytes() + " bytes left over");
        }
        left = BUDGET;
        line.add("value", tree(packet, new IdentityHashMap<>(), 0));
        if (left < 0) {
            line.addProperty("error", "over " + BUDGET + " values");
        }
    }

    // The value as plain JSON. `path` holds what's being walked, so a cycle ends.
    private static JsonElement tree(Object v, IdentityHashMap<Object, Boolean> path, int depth) {
        if (v == null) {
            return JsonNull.INSTANCE;
        }
        if (--left < 0) {
            return new JsonPrimitive("<too big>");
        }
        if (depth > 64) {
            return new JsonPrimitive("<too deep>");
        }
        if (v instanceof String s) {
            return new JsonPrimitive(s);
        }
        if (v instanceof Boolean b) {
            return new JsonPrimitive(b);
        }
        if (v instanceof Character c) {
            return new JsonPrimitive(c.toString());
        }
        if (v instanceof Float f) {
            return f.isNaN() || f.isInfinite() ? new JsonPrimitive(f.toString()) : new JsonPrimitive(f);
        }
        if (v instanceof Double d) {
            return d.isNaN() || d.isInfinite() ? new JsonPrimitive(d.toString()) : new JsonPrimitive(d);
        }
        if (v instanceof Number n) {
            return new JsonPrimitive(n);
        }
        if (v instanceof Enum<?> e) {
            return new JsonPrimitive(e.name());
        }
        if (v instanceof UUID || v instanceof BitSet || v instanceof Identifier || v instanceof ResourceKey<?> || v instanceof Component) {
            return new JsonPrimitive(v.toString());
        }
        if (v instanceof Tag t) {
            return nbt(t);
        }
        String registered = REGISTERED.get(v);
        if (registered != null) {
            return new JsonPrimitive(registered);
        }
        if (v.getClass().isHidden() || v.getClass().isSynthetic()) {
            return new JsonPrimitive("<function>");
        }
        if (v instanceof Holder<?> h) {
            if (h instanceof Holder.Reference<?> r) {
                return new JsonPrimitive("#" + r.getRegisteredName());
            }
            return tree(h.value(), path, depth + 1);
        }
        if (v instanceof ItemStack stack) {
            if (stack.isEmpty()) {
                return new JsonPrimitive("empty");
            }
            JsonObject o = new JsonObject();
            o.addProperty("item", stack.typeHolder().getRegisteredName());
            o.addProperty("count", stack.getCount());
            o.addProperty("components", stack.getComponentsPatch().toString());
            return o;
        }
        if (v instanceof Optional<?> o) {
            return o.isPresent() ? tree(o.get(), path, depth + 1) : JsonNull.INSTANCE;
        }
        if (v instanceof OptionalInt o) {
            return o.isPresent() ? new JsonPrimitive(o.getAsInt()) : JsonNull.INSTANCE;
        }
        if (v instanceof OptionalLong o) {
            return o.isPresent() ? new JsonPrimitive(o.getAsLong()) : JsonNull.INSTANCE;
        }
        if (v instanceof OptionalDouble o) {
            return o.isPresent() ? new JsonPrimitive(o.getAsDouble()) : JsonNull.INSTANCE;
        }
        if (v instanceof byte[] b) {
            if (b.length <= 64) {
                return new JsonPrimitive(HexFormat.of().formatHex(b));
            }
            return new JsonPrimitive(b.length + " bytes, sha256 " + sha256(b));
        }
        if (path.containsKey(v)) {
            return new JsonPrimitive("<cycle>");
        }
        path.put(v, true);
        try {
            if (v.getClass().isArray()) {
                JsonArray a = new JsonArray();
                for (int i = 0; i < Array.getLength(v); i++) {
                    a.add(tree(Array.get(v, i), path, depth + 1));
                }
                return a;
            }
            if (v instanceof Map<?, ?> m) {
                List<JsonArray> entries = new ArrayList<>();
                for (Map.Entry<?, ?> e : m.entrySet()) {
                    JsonArray pair = new JsonArray();
                    pair.add(tree(e.getKey(), path, depth + 1));
                    pair.add(tree(e.getValue(), path, depth + 1));
                    entries.add(pair);
                }
                entries.sort(Comparator.comparing(p -> p.get(0).toString()));
                JsonArray a = new JsonArray();
                entries.forEach(a::add);
                return a;
            }
            if (v instanceof Collection<?> c) {
                List<JsonElement> items = new ArrayList<>();
                for (Object x : c) {
                    items.add(tree(x, path, depth + 1));
                }
                if (v instanceof Set<?>) {
                    items.sort(Comparator.comparing(JsonElement::toString));
                }
                JsonArray a = new JsonArray();
                items.forEach(a::add);
                return a;
            }
            if (v instanceof Record r) {
                JsonObject o = new JsonObject();
                o.addProperty("@", v.getClass().getSimpleName());
                for (RecordComponent c : r.getClass().getRecordComponents()) {
                    try {
                        var get = c.getAccessor();
                        get.setAccessible(true);
                        o.add(c.getName(), tree(get.invoke(r), path, depth + 1));
                    } catch (ReflectiveOperationException | RuntimeException e) {
                        o.addProperty(c.getName(), "<" + e + ">");
                    }
                }
                return o;
            }
            String pkg = v.getClass().getPackageName();
            if (pkg.startsWith("net.minecraft") || pkg.startsWith("com.mojang")) {
                JsonObject o = new JsonObject();
                o.addProperty("@", v.getClass().getSimpleName());
                for (Class<?> k = v.getClass(); k != null && k != Object.class; k = k.getSuperclass()) {
                    for (Field f : k.getDeclaredFields()) {
                        if (Modifier.isStatic(f.getModifiers()) || f.isSynthetic()) {
                            continue;
                        }
                        try {
                            f.setAccessible(true);
                            o.add(f.getName(), tree(f.get(v), path, depth + 1));
                        } catch (ReflectiveOperationException | RuntimeException e) {
                            o.addProperty(f.getName(), "<" + e + ">");
                        }
                    }
                }
                return o;
            }
            // Anything else is named by its type, unless its own text says more than its address.
            String text = v.toString();
            return new JsonPrimitive(text.matches(".*@[0-9a-f]{4,}.*") ? v.getClass().getName() : text);
        } finally {
            path.remove(v);
        }
    }

    // A tag as SNBT, except compounds and lists, which are trees, compounds sorted by key.
    private static JsonElement nbt(Tag t) {
        if (t instanceof CompoundTag c) {
            JsonObject o = new JsonObject();
            c.keySet().stream().sorted().forEach(k -> o.add(k, nbt(c.get(k))));
            return o;
        }
        if (t instanceof ListTag l) {
            JsonArray a = new JsonArray();
            for (Tag x : l) {
                a.add(nbt(x));
            }
            return a;
        }
        return new JsonPrimitive(t.toString());
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).substring(0, 16);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String stateName(int state) {
        return switch (state) {
            case 1 -> "status";
            case 2 -> "login";
            case 3 -> "configuration";
            case 4 -> "play";
            default -> "state " + state;
        };
    }
}
