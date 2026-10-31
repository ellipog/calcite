package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import it.unimi.dsi.fastutil.ints.Int2IntMap;
import it.unimi.dsi.fastutil.ints.Int2IntOpenHashMap;
import it.unimi.dsi.fastutil.ints.IntIterator;
import it.unimi.dsi.fastutil.ints.IntOpenHashSet;
import it.unimi.dsi.fastutil.longs.Long2IntMap;
import it.unimi.dsi.fastutil.longs.Long2IntOpenHashMap;
import it.unimi.dsi.fastutil.longs.LongIterator;
import it.unimi.dsi.fastutil.longs.LongOpenHashSet;
import it.unimi.dsi.fastutil.objects.Object2IntMap;
import it.unimi.dsi.fastutil.objects.Object2IntOpenHashMap;
import it.unimi.dsi.fastutil.objects.ObjectOpenHashSet;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.NavigableSet;
import java.util.PriorityQueue;
import java.util.SequencedMap;
import java.util.SequencedSet;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * `collections`: operations on one of the Java and fastutil collections whose order vanilla's
 * behaviour shows, with each result and the iteration order when asked (rig/PROTOCOL.md).
 */
final class CollectionsProbe implements Probe {
    @Override
    public String name() {
        return "collections";
    }

    @Override
    public int version() {
        return 1;
    }

    /** The key type: `Integer`, `Long` or `String` keys. */
    private enum Kind {
        INT, LONG, STRING;

        Object parse(String text, String what) {
            return switch (this) {
                case INT -> {
                    try {
                        yield Integer.parseInt(text);
                    } catch (NumberFormatException e) {
                        throw new CaseError(what + " must be a decimal 32-bit integer");
                    }
                }
                case LONG -> Args.parseLong(text, what);
                case STRING -> text;
            };
        }

        void write(DataOutputStream out, Object key) throws IOException {
            switch (this) {
                case INT -> out.writeInt((Integer) key);
                case LONG -> out.writeLong((Long) key);
                case STRING -> {
                    byte[] bytes = ((String) key).getBytes(StandardCharsets.UTF_8);
                    out.writeInt(bytes.length);
                    out.write(bytes);
                }
            }
        }

        /** `remove_iter`'s test: the key, or a string's length, is `r` modulo `m`. */
        boolean picks(Object key, int m, int r) {
            long v = switch (this) {
                case INT -> (Integer) key;
                case LONG -> (Long) key;
                case STRING -> ((String) key).length();
            };
            return Math.floorMod(v, (long) m) == r;
        }
    }

    /** One operation: its name and its arguments, read as keys and values. */
    private record Op(JsonArray items, int index, Kind kind) {
        String name() {
            return Args.asString(items.get(0), "operation " + index + "'s name");
        }

        void expect(int n) {
            if (items.size() != n + 1) {
                throw new CaseError("operation " + index + ": `" + name() + "` takes " + n + " arguments, got " + (items.size() - 1));
            }
        }

        Object key(int i) {
            return kind.parse(Args.asString(items.get(i), "operation " + index + "'s key"), "operation " + index + "'s key");
        }

        int value(int i) {
            return Args.asInt(items.get(i), "operation " + index + "'s argument " + i);
        }
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        String collection = Args.string(input, "collection");
        String keyName = Args.string(input, "key");
        Kind kind = switch (keyName) {
            case "int" -> Kind.INT;
            case "long" -> Kind.LONG;
            case "string" -> Kind.STRING;
            default -> throw new CaseError("unknown key type `" + keyName + "`");
        };
        Integer capacity = input.has("capacity") ? Args.asInt(input.get("capacity"), "`capacity`") : null;
        if (capacity != null && !List.of("hash_map", "hash_set", "open_hash_map", "open_hash_set").contains(collection)) {
            throw new CaseError("`capacity` applies only to hash_map, hash_set, open_hash_map and open_hash_set");
        }
        if (capacity != null && capacity < 0) {
            throw new CaseError("`capacity` must not be negative");
        }
        JsonArray ops = Args.array(input, "ops");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        Target target = create(collection, kind, capacity);
        for (int i = 0; i < ops.size(); i++) {
            if (!ops.get(i).isJsonArray() || ops.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + i + " must be a non-empty array");
            }
            Op op = new Op(ops.get(i).getAsJsonArray(), i, kind);
            if (!target.apply(op, out)) {
                throw new CaseError("operation " + i + ": `" + op.name() + "` doesn't apply to " + collection);
            }
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    /** A collection that runs operations: false if it has no such operation. */
    private interface Target {
        boolean apply(Op op, DataOutputStream out) throws IOException;
    }

    private static Target create(String collection, Kind kind, Integer capacity) {
        return switch (collection) {
            case "hash_map" -> new JavaMap(capacity == null ? new HashMap<>() : new HashMap<>(capacity), kind);
            case "linked_hash_map" -> new JavaMap(new LinkedHashMap<>(), kind);
            case "tree_map" -> new JavaMap(new TreeMap<>(), kind);
            case "hash_set" -> new JavaSet(capacity == null ? new HashSet<>() : new HashSet<>(capacity), kind);
            case "linked_hash_set" -> new JavaSet(new LinkedHashSet<>(), kind);
            case "tree_set" -> new JavaSet(new TreeSet<>(), kind);
            case "open_hash_map" -> switch (kind) {
                case INT -> new IntOpenMap(capacity == null ? new Int2IntOpenHashMap() : new Int2IntOpenHashMap(capacity));
                case LONG -> new LongOpenMap(capacity == null ? new Long2IntOpenHashMap() : new Long2IntOpenHashMap(capacity));
                case STRING -> new StringOpenMap(capacity == null ? new Object2IntOpenHashMap<>() : new Object2IntOpenHashMap<>(capacity));
            };
            case "open_hash_set" -> switch (kind) {
                case INT -> new OpenSet(capacity == null ? new IntOpenHashSet() : new IntOpenHashSet(capacity), kind);
                case LONG -> new OpenSet(capacity == null ? new LongOpenHashSet() : new LongOpenHashSet(capacity), kind);
                case STRING -> new OpenSet(capacity == null ? new ObjectOpenHashSet<String>() : new ObjectOpenHashSet<String>(capacity), kind);
            };
            case "priority_queue" -> new Queue(new PriorityQueue<>(), kind);
            case "array_deque" -> new Deque(new ArrayDeque<>(), kind);
            default -> throw new CaseError("unknown collection `" + collection + "`");
        };
    }

    // --- writing results ------------------------------------------------------------------------

    private static void bool(DataOutputStream out, boolean b) throws IOException {
        out.writeByte(b ? 1 : 0);
    }

    private static void maybeValue(DataOutputStream out, Integer v) throws IOException {
        if (v == null) {
            out.writeByte(0);
        } else {
            out.writeByte(1);
            out.writeInt(v);
        }
    }

    private static void maybeKey(DataOutputStream out, Kind kind, Object k) throws IOException {
        if (k == null) {
            out.writeByte(0);
        } else {
            out.writeByte(1);
            kind.write(out, k);
        }
    }

    private static void maybeEntry(DataOutputStream out, Kind kind, Map.Entry<Object, Integer> e) throws IOException {
        if (e == null) {
            out.writeByte(0);
        } else {
            out.writeByte(1);
            kind.write(out, e.getKey());
            out.writeInt(e.getValue());
        }
    }

    @SuppressWarnings("unchecked")
    private static int compare(Object a, Object b) {
        return ((Comparable<Object>) a).compareTo(b);
    }

    /** The keys from `a` up to but not including `b`, which mustn't come before `a`. */
    private static void range(DataOutputStream out, Op op, Kind kind, java.util.function.BiFunction<Object, Object, Iterable<Object>> keys)
            throws IOException {
        op.expect(2);
        Object a = op.key(1);
        Object b = op.key(2);
        if (compare(a, b) > 0) {
            throw new CaseError("operation " + op.index() + ": the range ends before it starts");
        }
        java.util.ArrayList<Object> found = new java.util.ArrayList<>();
        for (Object k : keys.apply(a, b)) {
            found.add(k);
        }
        out.writeInt(found.size());
        for (Object k : found) {
            kind.write(out, k);
        }
    }

    /**
     * `remove_iter` on one of fastutil's tables: a loop that removes the picked keys with the
     * iterator, as vanilla's `TicketStorage.removeTicketIf` and `ChunkMap.processUnloads` do. It
     * writes how many keys there were, then each in the order the loop went over them, which
     * isn't the table's order when a removal moves a key the loop hasn't reached past its end.
     */
    private static void removeIter(Op op, DataOutputStream out, Kind kind, int size, Iterator<?> keys,
                                   java.util.function.Function<Object, Object> keyOf) throws IOException {
        op.expect(2);
        int m = op.value(1);
        int r = op.value(2);
        if (m <= 0) {
            throw new CaseError("operation " + op.index() + ": the modulus must be positive");
        }
        out.writeInt(size);
        while (keys.hasNext()) {
            Object k = keyOf.apply(keys.next());
            kind.write(out, k);
            if (kind.picks(k, m, r)) {
                keys.remove();
            }
        }
    }

    // --- java.util maps -------------------------------------------------------------------------

    private record JavaMap(Map<Object, Integer> map, Kind kind) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "put" -> {
                    op.expect(2);
                    maybeValue(out, map.put(op.key(1), op.value(2)));
                }
                case "get" -> {
                    op.expect(1);
                    maybeValue(out, map.get(op.key(1)));
                }
                case "remove" -> {
                    op.expect(1);
                    maybeValue(out, map.remove(op.key(1)));
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, map.containsKey(op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                }
                case "clear" -> {
                    op.expect(0);
                    map.clear();
                }
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                    for (Map.Entry<Object, Integer> e : map.entrySet()) {
                        kind.write(out, e.getKey());
                        out.writeInt(e.getValue());
                    }
                }
                default -> {
                    return sequenced(op, out);
                }
            }
            return true;
        }

        /** What a `LinkedHashMap` and a `TreeMap` do at their ends, and a `TreeMap` between keys. */
        private boolean sequenced(Op op, DataOutputStream out) throws IOException {
            if (map instanceof HashMap<?, ?> && !(map instanceof LinkedHashMap<?, ?>)) {
                return false;
            }
            SequencedMap<Object, Integer> s = (SequencedMap<Object, Integer>) map;
            switch (op.name()) {
                case "first" -> {
                    op.expect(0);
                    Map.Entry<Object, Integer> e = s.firstEntry();
                    maybeKey(out, kind, e == null ? null : e.getKey());
                    return true;
                }
                case "last" -> {
                    op.expect(0);
                    Map.Entry<Object, Integer> e = s.lastEntry();
                    maybeKey(out, kind, e == null ? null : e.getKey());
                    return true;
                }
                case "poll_first" -> {
                    op.expect(0);
                    maybeEntry(out, kind, s.pollFirstEntry());
                    return true;
                }
                case "poll_last" -> {
                    op.expect(0);
                    maybeEntry(out, kind, s.pollLastEntry());
                    return true;
                }
                default -> {}
            }
            if (map instanceof LinkedHashMap<Object, Integer> linked) {
                switch (op.name()) {
                    case "put_first" -> {
                        op.expect(2);
                        maybeValue(out, linked.putFirst(op.key(1), op.value(2)));
                        return true;
                    }
                    case "put_last" -> {
                        op.expect(2);
                        maybeValue(out, linked.putLast(op.key(1), op.value(2)));
                        return true;
                    }
                    default -> {
                        return false;
                    }
                }
            }
            NavigableMap<Object, Integer> tree = (NavigableMap<Object, Integer>) map;
            switch (op.name()) {
                case "floor" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.floorKey(op.key(1)));
                }
                case "ceiling" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.ceilingKey(op.key(1)));
                }
                case "lower" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.lowerKey(op.key(1)));
                }
                case "higher" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.higherKey(op.key(1)));
                }
                case "range" -> range(out, op, kind, (a, b) -> tree.subMap(a, true, b, false).keySet());
                default -> {
                    return false;
                }
            }
            return true;
        }
    }

    // --- java.util sets -------------------------------------------------------------------------

    private record JavaSet(Set<Object> set, Kind kind) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "add" -> {
                    op.expect(1);
                    bool(out, set.add(op.key(1)));
                }
                case "remove" -> {
                    op.expect(1);
                    bool(out, set.remove(op.key(1)));
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, set.contains(op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(set.size());
                }
                case "clear" -> {
                    op.expect(0);
                    set.clear();
                }
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(set.size());
                    for (Object k : set) {
                        kind.write(out, k);
                    }
                }
                default -> {
                    return sequenced(op, out);
                }
            }
            return true;
        }

        private boolean sequenced(Op op, DataOutputStream out) throws IOException {
            if (set instanceof HashSet<?> && !(set instanceof LinkedHashSet<?>)) {
                return false;
            }
            SequencedSet<Object> s = (SequencedSet<Object>) set;
            switch (op.name()) {
                case "first" -> {
                    op.expect(0);
                    maybeKey(out, kind, s.isEmpty() ? null : s.getFirst());
                    return true;
                }
                case "last" -> {
                    op.expect(0);
                    maybeKey(out, kind, s.isEmpty() ? null : s.getLast());
                    return true;
                }
                case "poll_first" -> {
                    op.expect(0);
                    maybeKey(out, kind, s.isEmpty() ? null : s.removeFirst());
                    return true;
                }
                case "poll_last" -> {
                    op.expect(0);
                    maybeKey(out, kind, s.isEmpty() ? null : s.removeLast());
                    return true;
                }
                default -> {}
            }
            if (set instanceof LinkedHashSet<Object> linked) {
                switch (op.name()) {
                    case "add_first" -> {
                        op.expect(1);
                        linked.addFirst(op.key(1));
                        return true;
                    }
                    case "add_last" -> {
                        op.expect(1);
                        linked.addLast(op.key(1));
                        return true;
                    }
                    default -> {
                        return false;
                    }
                }
            }
            NavigableSet<Object> tree = (NavigableSet<Object>) set;
            switch (op.name()) {
                case "floor" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.floor(op.key(1)));
                }
                case "ceiling" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.ceiling(op.key(1)));
                }
                case "lower" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.lower(op.key(1)));
                }
                case "higher" -> {
                    op.expect(1);
                    maybeKey(out, kind, tree.higher(op.key(1)));
                }
                case "range" -> range(out, op, kind, (a, b) -> tree.subSet(a, true, b, false));
                default -> {
                    return false;
                }
            }
            return true;
        }
    }

    // --- fastutil's open maps, by their own methods -----------------------------------------------

    private record IntOpenMap(Int2IntOpenHashMap map) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "put" -> {
                    op.expect(2);
                    int k = (Integer) op.key(1);
                    boolean had = map.containsKey(k);
                    int old = map.put(k, op.value(2));
                    maybeValue(out, had ? old : null);
                }
                case "get" -> {
                    op.expect(1);
                    int k = (Integer) op.key(1);
                    maybeValue(out, map.containsKey(k) ? map.get(k) : null);
                }
                case "remove" -> {
                    op.expect(1);
                    int k = (Integer) op.key(1);
                    boolean had = map.containsKey(k);
                    int old = map.remove(k);
                    maybeValue(out, had ? old : null);
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, map.containsKey((int) (Integer) op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                }
                case "clear" -> {
                    op.expect(0);
                    map.clear();
                }
                case "trim" -> {
                    op.expect(0);
                    map.trim();
                }
                case "remove_iter" -> removeIter(op, out, Kind.INT, map.size(), map.int2IntEntrySet().fastIterator(),
                    e -> ((Int2IntMap.Entry) e).getIntKey());
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                    for (Int2IntMap.Entry e : map.int2IntEntrySet()) {
                        out.writeInt(e.getIntKey());
                        out.writeInt(e.getIntValue());
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        }
    }

    private record LongOpenMap(Long2IntOpenHashMap map) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "put" -> {
                    op.expect(2);
                    long k = (Long) op.key(1);
                    boolean had = map.containsKey(k);
                    int old = map.put(k, op.value(2));
                    maybeValue(out, had ? old : null);
                }
                case "get" -> {
                    op.expect(1);
                    long k = (Long) op.key(1);
                    maybeValue(out, map.containsKey(k) ? map.get(k) : null);
                }
                case "remove" -> {
                    op.expect(1);
                    long k = (Long) op.key(1);
                    boolean had = map.containsKey(k);
                    int old = map.remove(k);
                    maybeValue(out, had ? old : null);
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, map.containsKey((long) (Long) op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                }
                case "clear" -> {
                    op.expect(0);
                    map.clear();
                }
                case "trim" -> {
                    op.expect(0);
                    map.trim();
                }
                case "remove_iter" -> removeIter(op, out, Kind.LONG, map.size(), map.long2IntEntrySet().fastIterator(),
                    e -> ((Long2IntMap.Entry) e).getLongKey());
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                    for (Long2IntMap.Entry e : map.long2IntEntrySet()) {
                        out.writeLong(e.getLongKey());
                        out.writeInt(e.getIntValue());
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        }
    }

    private record StringOpenMap(Object2IntOpenHashMap<String> map) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "put" -> {
                    op.expect(2);
                    String k = (String) op.key(1);
                    boolean had = map.containsKey(k);
                    int old = map.put(k, op.value(2));
                    maybeValue(out, had ? old : null);
                }
                case "get" -> {
                    op.expect(1);
                    String k = (String) op.key(1);
                    maybeValue(out, map.containsKey(k) ? map.getInt(k) : null);
                }
                case "remove" -> {
                    op.expect(1);
                    String k = (String) op.key(1);
                    boolean had = map.containsKey(k);
                    int old = map.removeInt(k);
                    maybeValue(out, had ? old : null);
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, map.containsKey(op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                }
                case "clear" -> {
                    op.expect(0);
                    map.clear();
                }
                case "trim" -> {
                    op.expect(0);
                    map.trim();
                }
                case "remove_iter" -> removeIter(op, out, Kind.STRING, map.size(), map.object2IntEntrySet().fastIterator(),
                    e -> ((Object2IntMap.Entry<?>) e).getKey());
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(map.size());
                    for (Object2IntMap.Entry<String> e : map.object2IntEntrySet()) {
                        Kind.STRING.write(out, e.getKey());
                        out.writeInt(e.getIntValue());
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        }
    }

    /** fastutil's open sets, each by its own `add`, `remove`, `contains` and `trim`. */
    private record OpenSet(Object set, Kind kind) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "add" -> {
                    op.expect(1);
                    Object k = op.key(1);
                    bool(out, switch (set) {
                        case IntOpenHashSet s -> s.add((int) (Integer) k);
                        case LongOpenHashSet s -> s.add((long) (Long) k);
                        default -> strings().add((String) k);
                    });
                }
                case "remove" -> {
                    op.expect(1);
                    Object k = op.key(1);
                    bool(out, switch (set) {
                        case IntOpenHashSet s -> s.remove((int) (Integer) k);
                        case LongOpenHashSet s -> s.remove((long) (Long) k);
                        default -> strings().remove(k);
                    });
                }
                case "contains" -> {
                    op.expect(1);
                    Object k = op.key(1);
                    bool(out, switch (set) {
                        case IntOpenHashSet s -> s.contains((int) (Integer) k);
                        case LongOpenHashSet s -> s.contains((long) (Long) k);
                        default -> strings().contains(k);
                    });
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(((Set<?>) set).size());
                }
                case "clear" -> {
                    op.expect(0);
                    ((Set<?>) set).clear();
                }
                case "trim" -> {
                    op.expect(0);
                    switch (set) {
                        case IntOpenHashSet s -> s.trim();
                        case LongOpenHashSet s -> s.trim();
                        default -> strings().trim();
                    }
                }
                case "remove_iter" -> removeIter(op, out, kind, ((Set<?>) set).size(), ((Set<?>) set).iterator(), k -> k);
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(((Set<?>) set).size());
                    switch (set) {
                        case IntOpenHashSet s -> {
                            for (IntIterator it = s.iterator(); it.hasNext(); ) {
                                out.writeInt(it.nextInt());
                            }
                        }
                        case LongOpenHashSet s -> {
                            for (LongIterator it = s.iterator(); it.hasNext(); ) {
                                out.writeLong(it.nextLong());
                            }
                        }
                        default -> {
                            for (String k : strings()) {
                                Kind.STRING.write(out, k);
                            }
                        }
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        }

        @SuppressWarnings("unchecked")
        private ObjectOpenHashSet<String> strings() {
            return (ObjectOpenHashSet<String>) set;
        }
    }

    // --- queues ---------------------------------------------------------------------------------

    private record Queue(PriorityQueue<Object> queue, Kind kind) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "add" -> {
                    op.expect(1);
                    bool(out, queue.add(op.key(1)));
                }
                case "poll" -> {
                    op.expect(0);
                    maybeKey(out, kind, queue.poll());
                }
                case "peek" -> {
                    op.expect(0);
                    maybeKey(out, kind, queue.peek());
                }
                case "remove" -> {
                    op.expect(1);
                    bool(out, queue.remove(op.key(1)));
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, queue.contains(op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(queue.size());
                }
                case "clear" -> {
                    op.expect(0);
                    queue.clear();
                }
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(queue.size());
                    for (Object k : queue) {
                        kind.write(out, k);
                    }
                }
                case "remove_iter" -> {
                    // As vanilla's LevelChunkTicks.removeIf: a loop that removes with the
                    // iterator, which isn't what PriorityQueue.removeIf does.
                    op.expect(2);
                    int m = op.value(1);
                    int r = op.value(2);
                    if (m <= 0) {
                        throw new CaseError("operation " + op.index() + ": the modulus must be positive");
                    }
                    for (Iterator<Object> it = queue.iterator(); it.hasNext(); ) {
                        if (kind.picks(it.next(), m, r)) {
                            it.remove();
                        }
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        }
    }

    private record Deque(ArrayDeque<Object> deque, Kind kind) implements Target {
        @Override
        public boolean apply(Op op, DataOutputStream out) throws IOException {
            switch (op.name()) {
                case "add_first" -> {
                    op.expect(1);
                    deque.addFirst(op.key(1));
                }
                case "add_last" -> {
                    op.expect(1);
                    deque.addLast(op.key(1));
                }
                case "poll_first" -> {
                    op.expect(0);
                    maybeKey(out, kind, deque.pollFirst());
                }
                case "poll_last" -> {
                    op.expect(0);
                    maybeKey(out, kind, deque.pollLast());
                }
                case "first" -> {
                    op.expect(0);
                    maybeKey(out, kind, deque.peekFirst());
                }
                case "last" -> {
                    op.expect(0);
                    maybeKey(out, kind, deque.peekLast());
                }
                case "contains" -> {
                    op.expect(1);
                    bool(out, deque.contains(op.key(1)));
                }
                case "size" -> {
                    op.expect(0);
                    out.writeInt(deque.size());
                }
                case "clear" -> {
                    op.expect(0);
                    deque.clear();
                }
                case "iter" -> {
                    op.expect(0);
                    out.writeInt(deque.size());
                    for (Object k : deque) {
                        kind.write(out, k);
                    }
                }
                default -> {
                    return false;
                }
            }
            return true;
        }
    }
}
