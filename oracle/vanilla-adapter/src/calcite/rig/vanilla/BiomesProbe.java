package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.datafixers.util.Pair;
import com.mojang.serialization.JsonOps;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.IdentifierException;
import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeResolver;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.biome.MultiNoiseBiomeSource;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.densityfunction.SamplerContext;

/**
 * `biomes`: a biome source read as a dimension's generator writes it, with the climate of a
 * noise settings' router, asked for biomes at points, at climate targets and over chunks.
 */
final class BiomesProbe implements Probe {
    private static final int MAX_VALUES = 1 << 20;

    @Override
    public String name() {
        return "biomes";
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
        RuntimeException[] thrown = new RuntimeException[1];
        Thread thread = new Thread(() -> {
            try {
                result[0] = runCase(input, blobs);
            } catch (RuntimeException e) {
                thrown[0] = e;
            }
        }, "biomes case");
        thread.start();
        try {
            thread.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
        if (thrown[0] != null) {
            throw thrown[0];
        }
        return result[0];
    }

    private Result runCase(JsonObject input, List<byte[]> blobs) {
        RegistryAccess.Frozen access = RegistriesProbe.access();
        RegistryOps<JsonElement> ops = access.createSerializationContext(JsonOps.INSTANCE);
        long seed = Args.int64(input, "seed");
        Identifier id;
        try {
            id = Identifier.parse(Args.string(input, "settings"));
        } catch (IdentifierException e) {
            throw new CaseError("`settings` must be an identifier");
        }
        NoiseGeneratorSettings settings = access.lookupOrThrow(Registries.NOISE_SETTINGS)
                .get(ResourceKey.create(Registries.NOISE_SETTINGS, id))
                .orElseThrow(() -> new CaseError("no noise settings `" + id + "`"))
                .value();
        boolean cached = bool(input, "cached");
        JsonArray opList = Args.array(input, "ops");
        List<JsonArray> steps = new ArrayList<>();
        long reads = 0;
        long values = 0;
        String needsMulti = null;
        for (int i = 0; i < opList.size(); i++) {
            String what = "`ops`[" + i + "]";
            if (!opList.get(i).isJsonArray() || opList.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError(what + " must be a non-empty array");
            }
            JsonArray op = opList.get(i).getAsJsonArray();
            String kind = Args.asString(op.get(0), what + "[0]");
            switch (kind) {
                case "list" -> {
                    arity(op, 1, what);
                    needsMulti = what + ": `list` needs a `multi_noise` source";
                }
                case "climate", "points" -> {
                    arity(op, 2, what);
                    int n = count(op, what);
                    reads += 12L * n;
                    values += n;
                }
                case "search" -> {
                    arity(op, 2, what);
                    needsMulti = what + ": `search` needs a `multi_noise` source";
                    int n = count(op, what);
                    reads += 24L * n;
                    values += n;
                }
                case "chunk" -> {
                    arity(op, 5, what);
                    int minY = Args.asInt(op.get(3), what + "[3]");
                    int height = Args.asInt(op.get(4), what + "[4]");
                    if (minY % 16 != 0 || height % 16 != 0 || height <= 0 || minY < -2032 || minY + height > 2032) {
                        throw new CaseError(what + ": a chunk's `min_y` and `height` must be whole sections within the world");
                    }
                    Args.asInt(op.get(1), what + "[1]");
                    Args.asInt(op.get(2), what + "[2]");
                    values += height / 16 * 64L;
                }
                default -> throw new CaseError(what + ": unknown op `" + kind + "`");
            }
            steps.add(op);
        }
        if (values > MAX_VALUES) {
            throw new CaseError("the ops give more than " + MAX_VALUES + " values");
        }
        ByteBuffer args = ByteBuffer.wrap(Args.oneBlob(blobs));
        if (args.capacity() != reads) {
            throw new CaseError("the blob must hold " + reads + " bytes of ints");
        }
        // A source that doesn't read is compared only as that: the codec's messages are its own.
        var parsed = BiomeSource.CODEC.parse(ops, Args.field(input, "source"));
        if (parsed.isError()) {
            JsonObject invalid = new JsonObject();
            invalid.addProperty("invalid", true);
            return Result.ok(invalid);
        }
        BiomeSource source = parsed.getOrThrow();
        if (needsMulti != null && !(source instanceof MultiNoiseBiomeSource)) {
            throw new CaseError(needsMulti);
        }
        Map<Holder<Biome>, Integer> named = new LinkedHashMap<>();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        JsonArray possible = new JsonArray();
        try {
            for (Holder<Biome> biome : source.possibleBiomes()) {
                possible.add(name(biome));
            }
            RandomState state = RandomState.create(access.lookupOrThrow(Registries.NOISE), seed, settings);
            SamplerContext context = cached ? SamplerContext.builder().enableCaches().build() : SamplerContext.EMPTY_UNCACHED;
            Climate.Sampler sampler = state.createClimateSampler(context);
            BiomeResolver resolver = source.createResolver(sampler);
            for (JsonArray op : steps) {
                switch (op.get(0).getAsString()) {
                    case "list" -> {
                        List<Pair<Climate.ParameterPoint, Holder<Biome>>> list = parameters((MultiNoiseBiomeSource) source).values();
                        out.writeInt(list.size());
                        for (Pair<Climate.ParameterPoint, Holder<Biome>> entry : list) {
                            Climate.ParameterPoint p = entry.getFirst();
                            for (Climate.Parameter q : List.of(p.temperature(), p.humidity(), p.continentalness(), p.erosion(), p.depth(), p.weirdness())) {
                                out.writeLong(q.min());
                                out.writeLong(q.max());
                            }
                            out.writeLong(p.offset());
                            out.writeInt(index(named, entry.getSecond()));
                        }
                    }
                    case "climate" -> {
                        int n = op.get(1).getAsInt();
                        for (int i = 0; i < n; i++) {
                            Climate.TargetPoint t = sampler.sample(args.getInt(), args.getInt(), args.getInt());
                            out.writeLong(t.temperature());
                            out.writeLong(t.humidity());
                            out.writeLong(t.continentalness());
                            out.writeLong(t.erosion());
                            out.writeLong(t.depth());
                            out.writeLong(t.weirdness());
                        }
                    }
                    case "points" -> {
                        int n = op.get(1).getAsInt();
                        for (int i = 0; i < n; i++) {
                            out.writeInt(index(named, resolver.getNoiseBiome(args.getInt(), args.getInt(), args.getInt())));
                        }
                    }
                    case "search" -> {
                        int n = op.get(1).getAsInt();
                        MultiNoiseBiomeSource multi = (MultiNoiseBiomeSource) source;
                        for (int i = 0; i < n; i++) {
                            Climate.TargetPoint t = new Climate.TargetPoint(
                                    args.getInt(), args.getInt(), args.getInt(), args.getInt(), args.getInt(), args.getInt());
                            out.writeInt(index(named, multi.getNoiseBiome(t)));
                        }
                    }
                    case "chunk" -> {
                        int chunkX = op.get(1).getAsInt();
                        int chunkZ = op.get(2).getAsInt();
                        int minY = op.get(3).getAsInt();
                        int height = op.get(4).getAsInt();
                        // As ChunkGenerator.doCreateBiomes and ChunkAccess.fillBiomesFromNoise do.
                        Climate.Sampler chunkSampler = state.createClimateSampler(SamplerContext.builder().enableCaches().build());
                        int quartX = QuartPos.fromBlock(chunkX * 16);
                        int quartZ = QuartPos.fromBlock(chunkZ * 16);
                        BiomeResolver chunk = source.createResolverForChunk(
                                chunkSampler, quartX, QuartPos.fromBlock(minY), quartZ, 4, QuartPos.fromBlock(height), 4);
                        for (int sectionY = minY >> 4; sectionY < (minY + height) >> 4; sectionY++) {
                            int quartY = QuartPos.fromSection(sectionY);
                            for (int x = 0; x < 4; x++) {
                                for (int y = 0; y < 4; y++) {
                                    for (int z = 0; z < 4; z++) {
                                        out.writeInt(index(named, chunk.getNoiseBiome(quartX + x, quartY + y, quartZ + z)));
                                    }
                                }
                            }
                        }
                    }
                    default -> throw new IllegalStateException();
                }
            }
        } catch (CaseError e) {
            throw e;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        } catch (RuntimeException e) {
            return Result.rejected(e);
        }
        JsonArray biomes = new JsonArray();
        for (Holder<Biome> biome : named.keySet()) {
            biomes.add(name(biome));
        }
        JsonObject output = new JsonObject();
        output.add("possible", possible);
        output.add("biomes", biomes);
        return Result.ok(output, bytes.toByteArray());
    }

    @SuppressWarnings("unchecked")
    private static Climate.ParameterList<Holder<Biome>> parameters(MultiNoiseBiomeSource source) {
        try {
            Method method = MultiNoiseBiomeSource.class.getDeclaredMethod("parameters");
            method.setAccessible(true);
            return (Climate.ParameterList<Holder<Biome>>) method.invoke(source);
        } catch (NoSuchMethodException | IllegalAccessException e) {
            throw new IllegalStateException(e);
        } catch (InvocationTargetException e) {
            if (e.getCause() instanceof RuntimeException r) {
                throw r;
            }
            throw new IllegalStateException(e);
        }
    }

    private static int index(Map<Holder<Biome>, Integer> named, Holder<Biome> biome) {
        return named.computeIfAbsent(biome, b -> named.size());
    }

    private static String name(Holder<Biome> biome) {
        return biome.unwrapKey().map(k -> k.identifier().toString()).orElse("<inline>");
    }

    private static void arity(JsonArray op, int size, String what) {
        if (op.size() != size) {
            throw new CaseError(what + " must have " + size + " elements");
        }
    }

    private static int count(JsonArray op, String what) {
        int n = Args.asInt(op.get(1), what + "[1]");
        if (n < 0) {
            throw new CaseError(what + "'s count must not be negative");
        }
        return n;
    }

    private static boolean bool(JsonObject input, String name) {
        JsonElement value = Args.field(input, name);
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("`" + name + "` must be true or false");
        }
        return value.getAsBoolean();
    }
}
