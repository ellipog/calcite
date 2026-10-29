package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.DataResult;
import io.netty.buffer.Unpooled;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;
import java.util.stream.LongStream;
import net.minecraft.core.IdMap;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.util.SimpleBitStorage;
import net.minecraft.world.level.chunk.PalettedContainer;
import net.minecraft.world.level.chunk.PalettedContainerRO;
import net.minecraft.world.level.chunk.Strategy;

/**
 * `palette`: vanilla's PalettedContainer and SimpleBitStorage, run by a list of operations, each
 * result written to one blob (rig/PROTOCOL.md).
 */
final class PaletteProbe implements Probe {
    @Override
    public String name() {
        return "palette";
    }

    @Override
    public int version() {
        return 1;
    }

    /** A registry value: an object of its own, which palettes compare by identity, as block states. */
    private static final class Value {
        final int id;

        Value(int id) {
            this.id = id;
        }
    }

    /** A registry of values numbered from 0, each its own ID. */
    private static final class Registry implements IdMap<Value> {
        private final Value[] values;

        Registry(int size) {
            values = new Value[size];
            for (int i = 0; i < size; i++) {
                values[i] = new Value(i);
            }
        }

        @Override
        public int getId(Value thing) {
            return thing != null && thing.id < values.length && values[thing.id] == thing ? thing.id : -1;
        }

        @Override
        public Value byId(int id) {
            return id >= 0 && id < values.length ? values[id] : null;
        }

        @Override
        public int size() {
            return values.length;
        }

        @Override
        public Iterator<Value> iterator() {
            return Arrays.asList(values).iterator();
        }

        Value value(JsonElement item, String what) {
            int id = Args.asInt(item, what);
            if (id < 0 || id >= values.length) {
                throw new CaseError(what + " must be from 0 to " + (values.length - 1));
            }
            return values[id];
        }
    }

    /** The probe's 64-bit LCG. */
    private static final class Draws {
        private long x;

        Draws(long seed) {
            x = seed;
        }

        int next() {
            x = x * 6364136223846793005L + 1442695040888963407L;
            return (int) (x >>> 33);
        }
    }

    /** One operation: its name and its arguments. */
    private record Op(JsonArray items, int index) {
        String name() {
            return Args.asString(items.get(0), "operation " + index + "'s name");
        }

        void expect(int n) {
            if (items.size() != n + 1) {
                throw new CaseError("operation " + index + ": `" + name() + "` takes " + n + " arguments, got " + (items.size() - 1));
            }
        }

        JsonElement arg(int i) {
            return items.get(i);
        }

        String what(int i) {
            return "operation " + index + "'s argument " + i;
        }

        int number(int i) {
            return Args.asInt(items.get(i), what(i));
        }

        /** An index below `size`. */
        int index(int i, int size) {
            int n = number(i);
            if (n < 0 || n >= size) {
                throw new CaseError(what(i) + " must be an index below " + size);
            }
            return n;
        }

        Draws draws() {
            return new Draws(Args.parseLong(Args.asString(items.get(1), what(1)), what(1)));
        }
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        if (!blobs.isEmpty()) {
            throw new CaseError("`palette` takes no blobs");
        }
        JsonArray ops = Args.array(input, "ops");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        switch (Args.string(input, "of")) {
            case "container" -> container(input, ops, out);
            case "storage" -> storage(input, ops, out);
            default -> throw new CaseError("`of` must be container or storage");
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    private static Op op(JsonArray ops, int i) {
        if (!ops.get(i).isJsonArray() || ops.get(i).getAsJsonArray().isEmpty()) {
            throw new CaseError("operation " + i + " must be a non-empty array");
        }
        return new Op(ops.get(i).getAsJsonArray(), i);
    }

    private static void container(JsonObject input, JsonArray ops, DataOutputStream out) throws IOException {
        int size = Args.asInt(Args.field(input, "registry"), "`registry`");
        if (size < 1 || size > 1 << 20) {
            throw new CaseError("`registry` must be from 1 to 1048576");
        }
        Registry registry = new Registry(size);
        String kind = Args.string(input, "strategy");
        Strategy<Value> strategy = switch (kind) {
            case "block_states" -> Strategy.createForBlockStates(registry);
            case "biomes" -> Strategy.createForBiomes(registry);
            default -> throw new CaseError("`strategy` must be block_states or biomes");
        };
        int axis = kind.equals("block_states") ? 4 : 2;
        int side = (1 << axis) - 1;
        int entries = strategy.entryCount();
        PalettedContainer<Value> c = new PalettedContainer<>(registry.value(Args.field(input, "value"), "`value`"), strategy);
        for (int k = 0; k < ops.size(); k++) {
            Op op = op(ops, k);
            switch (op.name()) {
                case "set" -> {
                    op.expect(2);
                    int i = op.index(1, entries);
                    c.set(i & side, i >> (2 * axis), (i >> axis) & side, registry.value(op.arg(2), op.what(2)));
                }
                case "get" -> {
                    op.expect(1);
                    int i = op.index(1, entries);
                    out.writeInt(c.get(i & side, i >> (2 * axis), (i >> axis) & side).id);
                }
                case "get_and_set" -> {
                    op.expect(2);
                    int i = op.index(1, entries);
                    out.writeInt(c.getAndSet(i & side, i >> (2 * axis), (i >> axis) & side, registry.value(op.arg(2), op.what(2))).id);
                }
                case "random_sets" -> {
                    op.expect(4);
                    Draws draws = op.draws();
                    int count = op.number(2);
                    Value low = registry.value(op.arg(3), op.what(3));
                    int high = op.number(4);
                    if (high <= low.id || high > size) {
                        throw new CaseError(op.what(4) + " must be above the low value and at most the registry's size");
                    }
                    for (int n = 0; n < count; n++) {
                        int i = draws.next() % entries;
                        Value v = registry.byId(low.id + draws.next() % (high - low.id));
                        c.set(i & side, i >> (2 * axis), (i >> axis) & side, v);
                    }
                }
                case "bits" -> {
                    op.expect(0);
                    out.writeInt(c.bitsPerEntry());
                }
                case "write" -> {
                    op.expect(0);
                    FriendlyByteBuf buf = new FriendlyByteBuf(Unpooled.buffer());
                    c.write(buf);
                    byte[] sent = new byte[buf.readableBytes()];
                    buf.readBytes(sent);
                    out.writeInt(sent.length);
                    out.write(sent);
                }
                case "pack" -> {
                    op.expect(0);
                    PalettedContainerRO.PackedData<Value> packed = c.pack(strategy);
                    out.writeInt(packed.paletteEntries().size());
                    for (Value v : packed.paletteEntries()) {
                        out.writeInt(v.id);
                    }
                    Optional<LongStream> data = packed.storage();
                    if (data.isEmpty()) {
                        out.writeByte(0);
                    } else {
                        long[] longs = data.get().toArray();
                        out.writeByte(1);
                        out.writeInt(longs.length);
                        for (long l : longs) {
                            out.writeLong(l);
                        }
                    }
                }
                case "unpack" -> {
                    op.expect(2);
                    if (!op.arg(1).isJsonArray()) {
                        throw new CaseError(op.what(1) + " must be an array");
                    }
                    List<Value> palette = new ArrayList<>();
                    for (JsonElement item : op.arg(1).getAsJsonArray()) {
                        palette.add(registry.value(item, op.what(1) + "'s entry"));
                    }
                    Optional<LongStream> data = op.arg(2).isJsonNull() ? Optional.empty() : Optional.of(LongStream.of(longs(op.arg(2), op.what(2))));
                    c = unpacked(c, PalettedContainer.unpack(strategy, new PalettedContainerRO.PackedData<>(palette, data)), out);
                }
                case "repack" -> {
                    op.expect(0);
                    c = unpacked(c, PalettedContainer.unpack(strategy, c.pack(strategy)), out);
                }
                case "counts" -> {
                    op.expect(0);
                    List<int[]> counts = new ArrayList<>();
                    c.count((v, n) -> counts.add(new int[] {v.id, n}));
                    counts.sort(Comparator.<int[]>comparingInt(p -> p[0]).thenComparingInt(p -> p[1]));
                    out.writeInt(counts.size());
                    for (int[] p : counts) {
                        out.writeInt(p[0]);
                        out.writeInt(p[1]);
                    }
                }
                default -> throw new CaseError("operation " + k + ": a container has no `" + op.name() + "`");
            }
        }
    }

    private static PalettedContainer<Value> unpacked(PalettedContainer<Value> c, DataResult<PalettedContainer<Value>> result, DataOutputStream out) throws IOException {
        Optional<PalettedContainer<Value>> unpacked = result.result();
        if (unpacked.isPresent()) {
            out.writeByte(0);
            return unpacked.get();
        }
        out.writeByte(1);
        message(out, result.error().orElseThrow().message());
        return c;
    }

    private static void storage(JsonObject input, JsonArray ops, DataOutputStream out) throws IOException {
        int bits = Args.asInt(Args.field(input, "bits"), "`bits`");
        int size = Args.asInt(Args.field(input, "size"), "`size`");
        if (bits < 1 || bits > 32) {
            throw new CaseError("`bits` must be from 1 to 32");
        }
        if (size < 0 || size > 4096) {
            throw new CaseError("`size` must be from 0 to 4096");
        }
        long mask = (1L << bits) - 1;
        SimpleBitStorage s = new SimpleBitStorage(bits, size);
        for (int k = 0; k < ops.size(); k++) {
            Op op = op(ops, k);
            switch (op.name()) {
                case "set" -> {
                    op.expect(2);
                    s.set(op.index(1, size), value(op, 2, mask));
                }
                case "fill" -> {
                    op.expect(1);
                    s.fill(value(op, 1, mask));
                }
                case "get" -> {
                    op.expect(1);
                    out.writeInt(s.get(op.index(1, size)));
                }
                case "get_and_set" -> {
                    op.expect(2);
                    out.writeInt(s.getAndSet(op.index(1, size), value(op, 2, mask)));
                }
                case "random_sets" -> {
                    op.expect(4);
                    if (size == 0) {
                        throw new CaseError("operation " + k + ": an empty storage has nowhere to set");
                    }
                    Draws draws = op.draws();
                    int count = op.number(2);
                    int low = value(op, 3, mask);
                    long high = Args.asInt(op.arg(4), op.what(4));
                    if (high <= low || high - 1 > mask) {
                        throw new CaseError(op.what(4) + " must be above the low value and fit the bits");
                    }
                    for (int n = 0; n < count; n++) {
                        int i = draws.next() % size;
                        s.set(i, (int) (low + draws.next() % (high - low)));
                    }
                }
                case "longs" -> {
                    op.expect(0);
                    long[] raw = s.getRaw();
                    out.writeInt(raw.length);
                    for (long l : raw) {
                        out.writeLong(l);
                    }
                }
                case "values" -> {
                    op.expect(0);
                    int[] values = new int[size];
                    s.unpack(values);
                    out.writeInt(values.length);
                    for (int v : values) {
                        out.writeInt(v);
                    }
                }
                case "load" -> {
                    op.expect(1);
                    long[] data = longs(op.arg(1), op.what(1));
                    try {
                        s = new SimpleBitStorage(bits, size, data);
                        out.writeByte(0);
                    } catch (SimpleBitStorage.InitializationException e) {
                        out.writeByte(1);
                        message(out, e.getMessage());
                    }
                }
                default -> throw new CaseError("operation " + k + ": a storage has no `" + op.name() + "`");
            }
        }
    }

    /** A value that fits in the storage's bits. */
    private static int value(Op op, int i, long mask) {
        int v = op.number(i);
        if (v < 0 || v > mask) {
            throw new CaseError(op.what(i) + " must be from 0 to " + mask);
        }
        return v;
    }

    private static long[] longs(JsonElement item, String what) {
        if (!item.isJsonArray()) {
            throw new CaseError(what + " must be an array or null");
        }
        JsonArray array = item.getAsJsonArray();
        long[] longs = new long[array.size()];
        for (int i = 0; i < longs.length; i++) {
            longs[i] = Args.parseLong(Args.asString(array.get(i), what + "'s long"), what + "'s long");
        }
        return longs;
    }

    private static void message(DataOutputStream out, String text) throws IOException {
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(bytes.length);
        out.write(bytes);
    }
}
