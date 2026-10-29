package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.datafixers.util.Pair;
import com.mojang.serialization.DynamicOps;
import it.unimi.dsi.fastutil.ints.IntList;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.LayeredRegistryAccess;
import net.minecraft.core.Registry;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.RegistrySynchronization;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryDataLoader;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.RegistryLayer;
import net.minecraft.server.WorldLoader;
import net.minecraft.server.packs.repository.KnownPack;
import net.minecraft.server.packs.repository.PackRepository;
import net.minecraft.server.packs.repository.ServerPacksSource;
import net.minecraft.server.packs.resources.CloseableResourceManager;
import net.minecraft.tags.TagLoader;
import net.minecraft.tags.TagNetworkSerialization;
import net.minecraft.world.level.WorldDataConfiguration;

/**
 * `registries`: what a server with only the vanilla data pack sends a client in configuration. The
 * registries are loaded once, as {@code WorldLoader.load} loads them, and kept.
 */
final class RegistriesProbe implements Probe {
    private static LayeredRegistryAccess<RegistryLayer> layers;
    private static List<KnownPack> knownPacks;

    @Override
    public String name() {
        return "registries";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        String op = Args.string(input, "op");
        return switch (op) {
            case "known_packs" -> knownPacks();
            case "synced" -> synced();
            case "tags" -> tags(Args.string(input, "registry"));
            default -> throw new CaseError("unknown `op`: `" + op + "`");
        };
    }

    /** Every registry the server has, with the vanilla data pack's, as a client is sent them. */
    static RegistryAccess.Frozen access() {
        load();
        return layers.compositeAccess();
    }

    private static synchronized void load() {
        if (layers != null) {
            return;
        }
        PackRepository repository = ServerPacksSource.createVanillaTrustedRepository();
        Pair<WorldDataConfiguration, CloseableResourceManager> packs =
            new WorldLoader.PackConfig(repository, WorldDataConfiguration.DEFAULT, false, true).createResourceManager();
        CloseableResourceManager resources = packs.getSecond();
        LayeredRegistryAccess<RegistryLayer> initial = RegistryLayer.createRegistryAccess();
        List<Registry.PendingTags<?>> staticTags = TagLoader.loadTagsForExistingRegistries(resources, initial.getLayer(RegistryLayer.STATIC));
        RegistryAccess.Frozen context = initial.getAccessForLoading(RegistryLayer.WORLD);
        List<HolderLookup.RegistryLookup<?>> contextRegistries = TagLoader.buildUpdatedLookups(context, staticTags);
        RegistryAccess.Frozen world = RegistryDataLoader.load(resources, contextRegistries, RegistryDataLoader.WORLD_REGISTRIES, Runnable::run).join();
        staticTags.forEach(Registry.PendingTags::apply);
        knownPacks = resources.listPacks().flatMap(p -> p.location().knownPackInfo().stream()).toList();
        layers = initial.replaceFrom(RegistryLayer.WORLD, world);
    }

    /** The server's known packs, which it offers in `select_known_packs`. */
    private static Result knownPacks() {
        load();
        JsonArray out = new JsonArray();
        for (KnownPack pack : knownPacks) {
            JsonArray p = new JsonArray();
            p.add(pack.namespace());
            p.add(pack.id());
            p.add(pack.version());
            out.add(p);
        }
        JsonObject output = new JsonObject();
        output.add("packs", out);
        return Result.ok(output);
    }

    /**
     * Each synchronized registry in the order `registry_data` packets go, with its entries in ID
     * order, and whether a client that knows the server's packs is sent each entry's data.
     */
    private static Result synced() {
        load();
        DynamicOps<Tag> ops = layers.compositeAccess().createSerializationContext(NbtOps.INSTANCE);
        JsonArray registries = new JsonArray();
        RegistrySynchronization.packRegistries(ops, layers.getAccessFrom(RegistryLayer.WORLD), Set.copyOf(knownPacks), (key, entries) -> {
            JsonObject r = new JsonObject();
            r.addProperty("name", key.identifier().toString());
            JsonArray list = new JsonArray();
            for (RegistrySynchronization.PackedRegistryEntry e : entries) {
                JsonArray entry = new JsonArray();
                entry.add(e.id().toString());
                entry.add(e.data().isPresent());
                list.add(entry);
            }
            r.add("entries", list);
            registries.add(r);
        });
        JsonObject output = new JsonObject();
        output.add("registries", registries);
        return Result.ok(output);
    }

    /**
     * The tags `update_tags` sends for the registry, by name in string order, each with its entries'
     * IDs in the order they're sent. None for a registry it sends no tags for.
     */
    private static Result tags(String registry) {
        load();
        Map<String, List<Integer>> sorted = new TreeMap<>();
        Map<ResourceKey<? extends Registry<?>>, TagNetworkSerialization.NetworkPayload> payloads = TagNetworkSerialization.serializeTagsToNetwork(layers);
        for (var entry : payloads.entrySet()) {
            if (!entry.getKey().identifier().toString().equals(registry)) {
                continue;
            }
            for (Map.Entry<Identifier, IntList> tag : entry.getValue().tags().entrySet()) {
                sorted.put(tag.getKey().toString(), new ArrayList<>(tag.getValue()));
            }
        }
        JsonArray out = new JsonArray();
        sorted.forEach((name, ids) -> {
            JsonArray t = new JsonArray();
            t.add(name);
            JsonArray values = new JsonArray();
            ids.forEach(values::add);
            t.add(values);
            out.add(t);
        });
        JsonObject output = new JsonObject();
        output.add("tags", out);
        return Result.ok(output);
    }
}
