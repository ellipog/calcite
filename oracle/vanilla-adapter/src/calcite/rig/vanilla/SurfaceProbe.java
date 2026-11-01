package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import it.unimi.dsi.fastutil.objects.ObjectOpenHashSet;
import net.minecraft.IdentifierException;
import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeManager;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.chunk.status.ChunkStatus;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseChunk;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.NoiseSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.WorldGenerationContext;
import net.minecraft.world.level.levelgen.densityfunction.SamplerContext;
import net.minecraft.world.level.levelgen.material.rule.MaterialRule;

/**
 * `surface`: a chunk filled with a noise settings' terrain shape and then given its materials,
 * as {@code NoiseBasedChunkGenerator.buildTerrain} does before its carvers: {@code doFill}, then
 * {@code MaterialSystem.buildSurface} in the same {@code NoiseChunk}, with the noise settings'
 * material rule or one the case writes out, and the biomes of a biome source.
 *
 * <p>The chunk and the eight around it get their biomes as {@code createBiomes} gives them; the
 * biome manager reads them as a {@code WorldGenRegion} does, and the possible biomes are those in
 * their palettes, as {@code ChunkStatusTasks.buildTerrain} collects them.
 */
final class SurfaceProbe implements Probe {
    private static final long MAX_VALUES = 1L << 22;

    @Override
    public String name() {
        return "surface";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        // A parameter list's search remembers its last result per thread, so each case runs on
        // a thread of its own, from no last result.
        Result[] result = new Result[1];
        Throwable[] thrown = new Throwable[1];
        Thread thread = new Thread(() -> {
            try {
                result[0] = runCase(input, blobs);
            } catch (Throwable e) {
                thrown[0] = e;
            }
        }, "surface case");
        thread.start();
        try {
            thread.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
        if (thrown[0] instanceof RuntimeException e) {
            throw e;
        }
        if (thrown[0] != null) {
            throw new IllegalStateException("the case threw", thrown[0]);
        }
        return result[0];
    }

    private Result runCase(JsonObject input, List<byte[]> blobs) {
        if (!blobs.isEmpty()) {
            throw new CaseError("`surface` takes no blobs");
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
        List<int[]> steps = new ArrayList<>();
        long values = 0;
        for (int i = 0; i < opList.size(); i++) {
            String what = "`ops`[" + i + "]";
            if (!opList.get(i).isJsonArray() || opList.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError(what + " must be a non-empty array");
            }
            JsonArray op = opList.get(i).getAsJsonArray();
            String kind = Args.asString(op.get(0), what + "[0]");
            if (!kind.equals("surface")) {
                throw new CaseError(what + ": unknown op `" + kind + "`");
            }
            if (op.size() != 3) {
                throw new CaseError(what + " must have 3 elements");
            }
            int a = Args.asInt(op.get(1), what + "[1]");
            int b = Args.asInt(op.get(2), what + "[2]");
            values += 256L * height;
            steps.add(new int[] {a, b});
        }
        if (values > MAX_VALUES) {
            throw new CaseError("the ops give more than " + MAX_VALUES + " values");
        }
        // A source or rule that doesn't read is compared only as that: the codecs' messages are
        // their own.
        var parsedSource = BiomeSource.CODEC.parse(ops, Args.field(input, "source"));
        if (parsedSource.isError()) {
            return invalid("source");
        }
        BiomeSource source = parsedSource.getOrThrow();
        MaterialRule rule;
        if (input.has("rule")) {
            var parsedRule = MaterialRule.CODEC.parse(ops, input.get("rule"));
            if (parsedRule.isError()) {
                // Only to the log: what reads it tells why.
                System.err.println("surface: rule doesn't read: " + parsedRule.error().orElseThrow().message());
                return invalid("rule");
            }
            rule = parsedRule.getOrThrow();
        } else {
            rule = settings.value().materialRule().value();
        }
        NoiseBasedChunkGenerator generator = new NoiseBasedChunkGenerator(source, settings);
        LevelHeightAccessor heights = LevelHeightAccessor.create(minY, height);
        PalettedContainerFactory containers = PalettedContainerFactory.create(access);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        try {
            RandomState state = RandomState.create(access.lookupOrThrow(Registries.NOISE), seed, settings.value());
            for (int[] op : steps) {
                surface(generator, settings.value(), state, source, seed, rule, heights, containers, op[0], op[1], out);
            }
        } catch (CaseError e) {
            throw e;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        } catch (RuntimeException e) {
            // Only to the log: where it threw.
            e.printStackTrace();
            return Result.rejected(e);
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    private static Result invalid(String what) {
        JsonObject invalid = new JsonObject();
        invalid.addProperty("invalid", what);
        return Result.ok(invalid);
    }

    /** {@code buildTerrain}'s fill and surface of the chunk at {@code chunkX}, {@code chunkZ}. */
    private static void surface(
            NoiseBasedChunkGenerator generator,
            NoiseGeneratorSettings settings,
            RandomState state,
            BiomeSource source,
            long seed,
            MaterialRule rule,
            LevelHeightAccessor heights,
            PalettedContainerFactory containers,
            int chunkX,
            int chunkZ,
            DataOutputStream out) throws IOException {
        // The chunk and its neighbours, with their biomes, as createBiomes gives them.
        Map<Long, ProtoChunk> chunks = new HashMap<>();
        ProtoChunk center = null;
        for (int dz = -1; dz <= 1; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                ChunkPos pos = new ChunkPos(chunkX + dx, chunkZ + dz);
                ProtoChunk chunk = new ProtoChunk(pos, UpgradeData.EMPTY, heights, containers, null);
                Climate.Sampler climate = state.createClimateSampler(SamplerContext.builder().enableCaches().build());
                chunk.fillBiomesFromNoise(source.createResolverForChunk(
                        climate,
                        QuartPos.fromBlock(pos.getMinBlockX()),
                        QuartPos.fromBlock(chunk.getMinY()),
                        QuartPos.fromBlock(pos.getMinBlockZ()),
                        QuartPos.fromBlock(16),
                        QuartPos.fromBlock(chunk.getHeight()),
                        QuartPos.fromBlock(16)));
                // Done with createBiomes, as the chunks around one at NOISE are.
                chunk.setPersistedStatus(ChunkStatus.BIOMES);
                chunks.put(pos.pack(), chunk);
                if (dx == 0 && dz == 0) {
                    center = chunk;
                }
            }
        }
        Set<Holder<Biome>> possibleBiomes = new ObjectOpenHashSet<>();
        for (int dz = -1; dz <= 1; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                chunks.get(ChunkPos.pack(chunkX + dx, chunkZ + dz)).collectBiomesInPalette(possibleBiomes);
            }
        }
        // As a WorldGenRegion reads biomes, from its chunks: the zoom only reaches a quart past
        // the chunk, so never past its neighbours.
        BiomeManager biomes = new BiomeManager((quartX, quartY, quartZ) -> {
            ProtoChunk chunk = chunks.get(ChunkPos.pack(QuartPos.toSection(quartX), QuartPos.toSection(quartZ)));
            if (chunk == null) {
                throw new IllegalStateException("a biome outside the chunk's neighbours");
            }
            return chunk.getNoiseBiome(quartX, quartY, quartZ);
        }, BiomeManager.obfuscateSeed(seed));
        NoiseSettings noise = settings.noiseSettings().clampToHeightAccessor(center.getHeightAccessorForGeneration());
        if (noise.height() > 0) {
            try (NoiseChunk noiseChunk = TerrainProbe.noiseChunk(generator, settings, state, center, noise)) {
                TerrainProbe.doFill(generator, noiseChunk, center);
                WorldGenerationContext context = new WorldGenerationContext(generator, center.getHeightAccessorForGeneration());
                state.surfaceSystem().buildSurface(state, biomes, context, center, noiseChunk, rule, possibleBiomes);
            }
        }
        TerrainProbe.write(center, out);
    }
}
