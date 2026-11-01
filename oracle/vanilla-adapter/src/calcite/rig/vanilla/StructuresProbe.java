package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.IdentifierException;
import net.minecraft.core.Holder;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.chunk.ChunkGeneratorStructureState;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.structure.Structure;
import net.minecraft.world.level.levelgen.structure.StructureSet;
import net.minecraft.world.level.levelgen.structure.StructureStart;
import net.minecraft.world.level.levelgen.structure.pieces.StructurePieceSerializationContext;
import net.minecraft.world.level.levelgen.structure.placement.ConcentricRingsStructurePlacement;
import net.minecraft.world.level.levelgen.structure.placement.StructurePlacement;

/**
 * `structures`: where 26.3's structure sets place structures, and the structure starts
 * {@code ChunkGenerator.createStructures} makes, through vanilla's own classes (rig/PROTOCOL.md).
 *
 * <p>The generator is a {@code NoiseBasedChunkGenerator} with the case's settings and biome source,
 * and its structure state is the one {@code createState} makes from every structure set in
 * vanilla's data, as a server makes it. A `starts` op runs {@code createStructures} on a fresh
 * {@code ProtoChunk} with a structure manager that only reads and writes that chunk's starts, as
 * the server's does for a chunk with none yet, and a template manager that loads vanilla's
 * templates, as the `features` probe's does.
 */
final class StructuresProbe implements Probe {
    private static final int MAX_OPS = 64;
    private static final int MAX_SQUARE = 256;

    @Override
    public String name() {
        return "structures";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`structures` takes no blobs");
        }
        RegistryAccess.Frozen access = RegistriesProbe.access();
        RegistryOps<JsonElement> ops = access.createSerializationContext(JsonOps.INSTANCE);
        long seed = Args.int64(input, "seed");
        Identifier id;
        try {
            id = Identifier.parse(Args.string(input, "settings"));
        } catch (IdentifierException e) {
            throw new CaseError("`settings` must be an identifier");
        }
        Holder<NoiseGeneratorSettings> settings = access.lookupOrThrow(Registries.NOISE_SETTINGS)
                .get(ResourceKey.create(Registries.NOISE_SETTINGS, id))
                .orElseThrow(() -> new CaseError("no noise settings `" + id + "`"));
        JsonArray level = Args.array(input, "level");
        if (level.size() != 2) {
            throw new CaseError("`level` must be [min_y, height]");
        }
        int minY = Args.asInt(level.get(0), "`level`[0]");
        int height = Args.asInt(level.get(1), "`level`[1]");
        if (minY % 16 != 0 || height % 16 != 0 || height <= 0 || minY < -2032 || minY + height > 2032) {
            throw new CaseError("`level` must be whole sections within the world");
        }
        JsonArray opList = Args.array(input, "ops");
        if (opList.size() > MAX_OPS) {
            throw new CaseError("at most " + MAX_OPS + " ops");
        }
        var parsedSource = BiomeSource.CODEC.parse(ops, Args.field(input, "source"));
        if (parsedSource.isError()) {
            JsonObject invalid = new JsonObject();
            invalid.addProperty("invalid", "source");
            return Result.ok(invalid);
        }
        BiomeSource source = parsedSource.getOrThrow();
        NoiseBasedChunkGenerator generator = new NoiseBasedChunkGenerator(source, settings);
        RandomState state = RandomState.create(access.lookupOrThrow(Registries.NOISE), seed, settings.value());
        ChunkGeneratorStructureState structures = generator.createState(access.lookupOrThrow(Registries.STRUCTURE_SET), state, seed);
        LevelHeightAccessor heights = LevelHeightAccessor.create(minY, height);
        PalettedContainerFactory containers = PalettedContainerFactory.create(access);
        FeaturesProbe.Templates templates = (FeaturesProbe.Templates) FeaturesProbe.allocate(FeaturesProbe.Templates.class);
        templates.loaded = new HashMap<>();
        templates.blocks = access.lookupOrThrow(Registries.BLOCK);
        ResourceKey<Level> dimension = id.getPath().equals("nether") ? Level.NETHER : id.getPath().equals("end") ? Level.END : Level.OVERWORLD;
        StructurePieceSerializationContext context = new StructurePieceSerializationContext(null, access, templates);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        for (int i = 0; i < opList.size(); i++) {
            String what = "`ops`[" + i + "]";
            if (!opList.get(i).isJsonArray() || opList.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError(what + " must be a non-empty array");
            }
            JsonArray op = opList.get(i).getAsJsonArray();
            String kind = Args.asString(op.get(0), what + "[0]");
            if (kind.equals("placement")) {
                if (op.size() != 4) {
                    throw new CaseError(what + " must have 4 elements");
                }
                int cx = Args.asInt(op.get(1), what + "[1]");
                int cz = Args.asInt(op.get(2), what + "[2]");
                int size = Args.asInt(op.get(3), what + "[3]");
                if (size < 1 || size > MAX_SQUARE) {
                    throw new CaseError(what + "[3] must be 1 to " + MAX_SQUARE);
                }
                placements(structures, cx, cz, size, out);
            } else if (kind.equals("rings")) {
                if (op.size() != 1) {
                    throw new CaseError(what + " must have 1 element");
                }
                rings(structures, out);
            } else if (kind.equals("starts")) {
                if (op.size() != 3) {
                    throw new CaseError(what + " must have 3 elements");
                }
                ChunkPos pos = new ChunkPos(Args.asInt(op.get(1), what + "[1]"), Args.asInt(op.get(2), what + "[2]"));
                ProtoChunk chunk = new ProtoChunk(pos, UpgradeData.EMPTY, heights, containers, null);
                StructureManager manager = (StructureManager) FeaturesProbe.allocate(StructureManager.class);
                generator.createStructures(access, structures, manager, chunk, templates, dimension);
                starts(context, chunk, out);
            } else if (kind.equals("ring_starts")) {
                if (op.size() != 2) {
                    throw new CaseError(what + " must have 2 elements");
                }
                int count = Args.asInt(op.get(1), what + "[1]");
                if (count < 0 || count > 16) {
                    throw new CaseError(what + "[1] must be 0 to 16");
                }
                // The starts at each concentric rings placement's first positions.
                for (Holder<StructureSet> set : structures.possibleStructureSets()) {
                    if (set.value().placement() instanceof ConcentricRingsStructurePlacement rings) {
                        List<ChunkPos> positions = structures.getRingPositionsFor(rings);
                        int n = positions == null ? 0 : Math.min(count, positions.size());
                        out.writeInt(n);
                        for (int k = 0; k < n; k++) {
                            ProtoChunk chunk = new ProtoChunk(positions.get(k), UpgradeData.EMPTY, heights, containers, null);
                            StructureManager manager = (StructureManager) FeaturesProbe.allocate(StructureManager.class);
                            generator.createStructures(access, structures, manager, chunk, templates, dimension);
                            starts(context, chunk, out);
                        }
                    }
                }
            } else {
                throw new CaseError(what + ": unknown op `" + kind + "`");
            }
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    /**
     * For each structure set the state may place, in its order: its ID, then how many chunks of
     * the square it places in and each one's {@code x} and {@code z}, {@code z} outer.
     */
    private static void placements(ChunkGeneratorStructureState structures, int cx, int cz, int size, DataOutputStream out) throws IOException {
        List<Holder<StructureSet>> sets = structures.possibleStructureSets();
        out.writeInt(sets.size());
        for (Holder<StructureSet> set : sets) {
            out.writeUTF(set.unwrapKey().orElseThrow().identifier().toString());
            StructurePlacement placement = set.value().placement();
            ByteArrayOutputStream found = new ByteArrayOutputStream();
            DataOutputStream chunks = new DataOutputStream(found);
            int count = 0;
            for (int z = cz; z < cz + size; z++) {
                for (int x = cx; x < cx + size; x++) {
                    if (placement.isStructureChunk(structures, x, z)) {
                        chunks.writeInt(x);
                        chunks.writeInt(z);
                        count++;
                    }
                }
            }
            out.writeInt(count);
            out.write(found.toByteArray());
        }
    }

    /**
     * For each structure set the state may place with concentric rings, in its order: its ID,
     * then how many ring positions it has, -1 for none worked out, and each one's {@code x} and
     * {@code z}.
     */
    private static void rings(ChunkGeneratorStructureState structures, DataOutputStream out) throws IOException {
        int count = 0;
        for (Holder<StructureSet> set : structures.possibleStructureSets()) {
            if (set.value().placement() instanceof ConcentricRingsStructurePlacement) {
                count++;
            }
        }
        out.writeInt(count);
        for (Holder<StructureSet> set : structures.possibleStructureSets()) {
            if (set.value().placement() instanceof ConcentricRingsStructurePlacement rings) {
                out.writeUTF(set.unwrapKey().orElseThrow().identifier().toString());
                List<ChunkPos> positions = structures.getRingPositionsFor(rings);
                if (positions == null) {
                    out.writeInt(-1);
                    continue;
                }
                out.writeInt(positions.size());
                for (ChunkPos p : positions) {
                    out.writeInt(p.x());
                    out.writeInt(p.z());
                }
            }
        }
    }

    /** The chunk's starts as a chunk's {@code structures.starts} compound saves them. */
    private static void starts(StructurePieceSerializationContext context, ProtoChunk chunk, DataOutputStream out) throws IOException {
        CompoundTag tag = new CompoundTag();
        var registry = context.registryAccess().lookupOrThrow(Registries.STRUCTURE);
        for (Map.Entry<Structure, StructureStart> e : chunk.getAllStarts().entrySet()) {
            tag.put(registry.getKey(e.getKey()).toString(), e.getValue().createTag(context, chunk.getPos()));
        }
        NbtIo.writeAnyTag(tag, out);
    }
}
