package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import it.unimi.dsi.fastutil.longs.Long2ObjectLinkedOpenHashMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectMap;
import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import it.unimi.dsi.fastutil.longs.LongIterator;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.TagParser;
import net.minecraft.resources.Identifier;
import net.minecraft.server.level.ChunkHolder;
import net.minecraft.server.level.ChunkLevel;
import net.minecraft.server.level.ChunkMap;
import net.minecraft.server.level.Ticket;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.TicketStorage;

/**
 * `tickets`: a dimension's chunk tickets, in vanilla's own {@link TicketStorage}, through a list
 * of operations, with what its two listeners are told as they're told it.
 *
 * <p>Purging stale tickets asks a {@link ChunkMap} for each chunk's holder, so `purge` gives it
 * one made without its constructor, whose only holders are those of the chunks the case says
 * are busy, made the same way, each with a save that hasn't finished. Reading `chunk_tickets`
 * parses its `data` with the type's own codec, as {@code SavedDataStorage.readSavedData} does,
 * logging the same line for what can't be read.
 */
final class TicketsProbe implements Probe {
    @Override
    public String name() {
        return "tickets";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`tickets` takes no blobs");
        }
        JsonArray ops = Args.array(input, "ops");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        TicketStorage storage = listened(new TicketStorage(), out);
        for (int k = 0; k < ops.size(); k++) {
            if (!ops.get(k).isJsonArray() || ops.get(k).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + k + " must be a non-empty array");
            }
            JsonArray op = ops.get(k).getAsJsonArray();
            String name = Args.asString(op.get(0), "operation " + k + "'s name");
            // Each operation's listener calls come first, as they're made, then a 0 and its result.
            ByteArrayOutputStream result = new ByteArrayOutputStream();
            DataOutputStream after = new DataOutputStream(result);
            switch (name) {
                case "add" -> {
                    expect(op, k, 3);
                    boolean added = storage.addTicket(chunk(op, k, 1), new Ticket(type(op, k, 2), integer(op, k, 3)));
                    after.writeBoolean(added);
                }
                case "add_radius" -> {
                    expect(op, k, 4);
                    storage.addTicketWithRadius(type(op, k, 1), new ChunkPos(integer(op, k, 2), integer(op, k, 3)), integer(op, k, 4));
                }
                case "remove" -> {
                    expect(op, k, 3);
                    boolean removed = storage.removeTicket(chunk(op, k, 1), new Ticket(type(op, k, 2), integer(op, k, 3)));
                    after.writeBoolean(removed);
                }
                case "remove_radius" -> {
                    expect(op, k, 4);
                    storage.removeTicketWithRadius(type(op, k, 1), new ChunkPos(integer(op, k, 2), integer(op, k, 3)), integer(op, k, 4));
                }
                case "forced" -> {
                    expect(op, k, 3);
                    after.writeBoolean(storage.updateChunkForced(new ChunkPos(integer(op, k, 1), integer(op, k, 2)), bool(op, k, 3)));
                }
                case "replace_level" -> {
                    expect(op, k, 2);
                    storage.replaceTicketLevelOfType(integer(op, k, 1), type(op, k, 2));
                }
                case "purge" -> {
                    expect(op, k, 1);
                    storage.purgeStaleTickets(chunkMap(op, k));
                }
                case "deactivate" -> {
                    expect(op, k, 0);
                    storage.deactivateTicketsOnClosing();
                }
                case "activate" -> {
                    expect(op, k, 0);
                    storage.activateAllDeactivatedTickets();
                }
                case "level" -> {
                    expect(op, k, 2);
                    after.writeInt(storage.getTicketLevelAt(chunk(op, k, 1), bool(op, k, 2)));
                }
                case "debug" -> {
                    expect(op, k, 2);
                    text(after, storage.getTicketDebugString(chunk(op, k, 1), bool(op, k, 2)));
                }
                case "dump" -> {
                    expect(op, k, 0);
                    dump(storage, after);
                }
                case "save" -> {
                    expect(op, k, 0);
                    after.writeBoolean(storage.isDirty());
                    root(after, (CompoundTag) TicketStorage.CODEC.encodeStart(NbtOps.INSTANCE, storage).getOrThrow());
                    storage.setDirty(false);
                }
                case "load" -> {
                    expect(op, k, 1);
                    CompoundTag tag;
                    try {
                        tag = TagParser.parseCompoundFully(Args.asString(op.get(1), "operation " + k + "'s SNBT")).copy();
                    } catch (Exception e) {
                        throw new CaseError("operation " + k + "'s SNBT isn't a compound: " + e.getMessage());
                    }
                    List<String> lines = new ArrayList<>();
                    // `readSavedData`'s parse, with its line.
                    TicketStorage read = TicketStorage.TYPE.codec()
                        .parse(NbtOps.INSTANCE, tag.get("data"))
                        .resultOrPartial(error -> lines.add("Failed to parse saved data for '" + TicketStorage.TYPE + "': " + error))
                        .orElse(null);
                    after.writeInt(lines.size());
                    for (String line : lines) {
                        text(after, line);
                    }
                    after.writeBoolean(read != null);
                    storage = listened(read != null ? read : new TicketStorage(), out);
                }
                default -> throw new CaseError("operation " + k + ": no operation `" + name + "`");
            }
            after.flush();
            out.writeByte(0);
            out.write(result.toByteArray());
        }
        out.flush();
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    // The storage with listeners that write each call to `out`: a 1, then 0 for the loading
    // tracker or 1 for the simulation tracker, the chunk, the level and whether it only went down.
    private static TicketStorage listened(TicketStorage storage, DataOutputStream out) {
        storage.setLoadingChunkUpdatedListener((node, level, onlyDecreased) -> told(out, 0, node, level, onlyDecreased));
        storage.setSimulationChunkUpdatedListener((node, level, onlyDecreased) -> told(out, 1, node, level, onlyDecreased));
        return storage;
    }

    private static void told(DataOutputStream out, int tracker, long node, int level, boolean onlyDecreased) {
        try {
            out.writeByte(1);
            out.writeByte(tracker);
            out.writeLong(node);
            out.writeInt(level);
            out.writeBoolean(onlyDecreased);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    // Whether it has tickets, keeps its dimension active and is dirty, then its tickets in use and
    // deactivated, each table in its order, then its forced chunks in their set's order.
    @SuppressWarnings("unchecked")
    private static void dump(TicketStorage storage, DataOutputStream out) throws Exception {
        out.writeBoolean(storage.hasTickets());
        out.writeBoolean(storage.shouldKeepDimensionActive());
        out.writeBoolean(storage.isDirty());
        for (String name : List.of("tickets", "deactivatedTickets")) {
            Field field = TicketStorage.class.getDeclaredField(name);
            field.setAccessible(true);
            Long2ObjectOpenHashMap<List<Ticket>> table = (Long2ObjectOpenHashMap<List<Ticket>>) field.get(storage);
            out.writeInt(table.size());
            for (Long2ObjectMap.Entry<List<Ticket>> entry : table.long2ObjectEntrySet()) {
                out.writeLong(entry.getLongKey());
                out.writeInt(entry.getValue().size());
                for (Ticket ticket : entry.getValue()) {
                    ticket(out, ticket);
                }
            }
        }
        out.writeInt(storage.getForceLoadedChunks().size());
        LongIterator forced = storage.getForceLoadedChunks().iterator();
        while (forced.hasNext()) {
            out.writeLong(forced.nextLong());
        }
    }

    // A ticket: its type's name, its level and the ticks it has left.
    private static void ticket(DataOutputStream out, Ticket ticket) throws Exception {
        Field left = Ticket.class.getDeclaredField("ticksLeft");
        left.setAccessible(true);
        text(out, BuiltInRegistries.TICKET_TYPE.getKey(ticket.getType()).toString());
        out.writeInt(ticket.getTicketLevel());
        out.writeLong(left.getLong(ticket));
    }

    // A chunk map with no constructor run, whose only holders are those of the busy chunks.
    private static ChunkMap chunkMap(JsonArray op, int k) throws Exception {
        if (!op.get(1).isJsonArray()) {
            throw new CaseError("operation " + k + "'s busy chunks must be an array");
        }
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field theUnsafe = unsafeClass.getDeclaredField("theUnsafe");
        theUnsafe.setAccessible(true);
        Object unsafe = theUnsafe.get(null);
        Method allocate = unsafeClass.getMethod("allocateInstance", Class.class);
        Long2ObjectLinkedOpenHashMap<ChunkHolder> holders = new Long2ObjectLinkedOpenHashMap<>();
        Field saveSync = ChunkHolder.class.getDeclaredField("saveSync");
        saveSync.setAccessible(true);
        for (JsonElement busy : op.get(1).getAsJsonArray()) {
            ChunkHolder holder = (ChunkHolder) allocate.invoke(unsafe, ChunkHolder.class);
            saveSync.set(holder, new CompletableFuture<>());
            holders.put(Args.parseLong(Args.asString(busy, "operation " + k + "'s busy chunk"), "operation " + k + "'s busy chunk"), holder);
        }
        ChunkMap map = (ChunkMap) allocate.invoke(unsafe, ChunkMap.class);
        Field updating = ChunkMap.class.getDeclaredField("updatingChunkMap");
        updating.setAccessible(true);
        updating.set(map, holders);
        return map;
    }

    private static void expect(JsonArray op, int k, int args) {
        if (op.size() != args + 1) {
            throw new CaseError("operation " + k + " takes " + args + " arguments");
        }
    }

    private static long chunk(JsonArray op, int k, int i) {
        return Args.parseLong(Args.asString(op.get(i), "operation " + k + "'s chunk"), "operation " + k + "'s chunk");
    }

    private static int integer(JsonArray op, int k, int i) {
        return Args.asInt(op.get(i), "operation " + k + "'s argument " + i);
    }

    private static boolean bool(JsonArray op, int k, int i) {
        JsonElement v = op.get(i);
        if (!v.isJsonPrimitive() || !v.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("operation " + k + "'s argument " + i + " must be a boolean");
        }
        return v.getAsBoolean();
    }

    private static TicketType type(JsonArray op, int k, int i) {
        String name = Args.asString(op.get(i), "operation " + k + "'s ticket type");
        TicketType type = BuiltInRegistries.TICKET_TYPE.getValue(Identifier.withDefaultNamespace(name));
        if (type == null || !BuiltInRegistries.TICKET_TYPE.containsKey(Identifier.withDefaultNamespace(name))) {
            throw new CaseError("operation " + k + ": no ticket type `" + name + "`");
        }
        return type;
    }

    // An `int` length, then the compound as `NbtIo.write` writes a file's root.
    private static void root(DataOutputStream out, CompoundTag tag) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        NbtIo.write(tag, new DataOutputStream(bytes));
        out.writeInt(bytes.size());
        out.write(bytes.toByteArray());
    }

    private static void text(DataOutputStream out, String text) throws IOException {
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        out.writeInt(bytes.length);
        out.write(bytes);
    }

    static {
        // The levels the cases are written for.
        if (ChunkLevel.MAX_LEVEL != 44) {
            throw new IllegalStateException("ChunkLevel.MAX_LEVEL is " + ChunkLevel.MAX_LEVEL + ", not 44");
        }
    }
}
