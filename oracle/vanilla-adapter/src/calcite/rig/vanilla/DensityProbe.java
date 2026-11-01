package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import net.minecraft.IdentifierException;
import net.minecraft.core.HolderGetter;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.util.Interval;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.NoiseRouter;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.densityfunction.DensityBuffer;
import net.minecraft.world.level.levelgen.densityfunction.DensityFunction;
import net.minecraft.world.level.levelgen.densityfunction.DensityFunctions;
import net.minecraft.world.level.levelgen.densityfunction.DensitySampler;
import net.minecraft.world.level.levelgen.densityfunction.DensityVolume;
import net.minecraft.world.level.levelgen.densityfunction.SamplerContext;
import net.minecraft.world.level.levelgen.synth.NormalNoise;

/**
 * `density`: density functions read as a data pack writes them, compiled by a `RandomState` and
 * sampled at points or over volumes, all through one sampler context.
 */
final class DensityProbe implements Probe {
    private static final int MAX_VOLUME = 65536;
    private static final int MAX_VALUES = 1 << 20;
    private static final List<String> ROUTER = List.of(
            "temperature", "vegetation", "continents", "erosion", "depth", "ridges", "chunk_surface_level", "final_density");

    @Override
    public String name() {
        return "density";
    }

    @Override
    public int version() {
        return 1;
    }

    private record Op(int function, DensityVolume volume, int points) {}

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        RegistryAccess.Frozen access = RegistriesProbe.access();
        RegistryOps<JsonElement> ops = access.createSerializationContext(JsonOps.INSTANCE);
        HolderGetter<NormalNoise> noises = access.lookupOrThrow(Registries.NOISE);
        long seed = Args.int64(input, "seed");
        NoiseGeneratorSettings settings = null;
        boolean legacy;
        if (input.has("settings")) {
            if (input.has("legacy_random")) {
                throw new CaseError("`legacy_random` comes from the settings");
            }
            Identifier id;
            try {
                id = Identifier.parse(Args.string(input, "settings"));
            } catch (IdentifierException e) {
                throw new CaseError("`settings` must be an identifier");
            }
            settings = access.lookupOrThrow(Registries.NOISE_SETTINGS)
                    .get(ResourceKey.create(Registries.NOISE_SETTINGS, id))
                    .orElseThrow(() -> new CaseError("no noise settings `" + id + "`"))
                    .value();
            legacy = settings.useLegacyRandomSource();
        } else {
            legacy = bool(input, "legacy_random");
        }
        List<DensityFunction> functions = new ArrayList<>();
        JsonArray list = Args.array(input, "functions");
        for (int i = 0; i < list.size(); i++) {
            String what = "`functions`[" + i + "]";
            if (!list.get(i).isJsonObject() || list.get(i).getAsJsonObject().size() != 1) {
                throw new CaseError(what + " must be an object with one field");
            }
            Map.Entry<String, JsonElement> entry = list.get(i).getAsJsonObject().entrySet().iterator().next();
            if (entry.getKey().equals("function")) {
                functions.add(DensityFunction.CODEC.parse(ops, entry.getValue())
                        .getOrThrow(message -> new CaseError(what + ": " + message)));
            } else if (entry.getKey().equals("router")) {
                if (settings == null) {
                    throw new CaseError(what + ": a router's field needs `settings`");
                }
                String field = Args.asString(entry.getValue(), what);
                functions.add(router(settings.noiseRouter(), field, what));
            } else {
                throw new CaseError(what + " must be `function` or `router`");
            }
        }
        boolean cached = bool(input, "cached");
        List<Op> steps = new ArrayList<>();
        long points = 0;
        long values = 0;
        JsonArray opList = Args.array(input, "ops");
        for (int i = 0; i < opList.size(); i++) {
            String what = "`ops`[" + i + "]";
            if (!opList.get(i).isJsonObject()) {
                throw new CaseError(what + " must be an object");
            }
            JsonObject op = opList.get(i).getAsJsonObject();
            int function = Args.asInt(Args.field(op, "fn"), what + "'s `fn`");
            if (function < 0 || function >= functions.size()) {
                throw new CaseError(what + "'s `fn` names no function");
            }
            if (op.has("points") == op.has("volume") || op.size() != 2) {
                throw new CaseError(what + " must have `fn` and one of `points` and `volume`");
            }
            if (op.has("points")) {
                int n = Args.asInt(op.get("points"), what + "'s `points`");
                if (n < 0) {
                    throw new CaseError(what + "'s `points` must not be negative");
                }
                steps.add(new Op(function, null, n));
                points += n;
                values += n;
            } else {
                DensityVolume volume = volume(Args.array(op, "volume"), what);
                steps.add(new Op(function, volume, 0));
                values += volume.size();
            }
        }
        if (values > MAX_VALUES) {
            throw new CaseError("the ops give more than " + MAX_VALUES + " values");
        }
        ByteBuffer args = ByteBuffer.wrap(Args.oneBlob(blobs));
        if (args.capacity() != points * 12) {
            throw new CaseError("the blob must hold " + points + " (x, y, z) int triples");
        }
        JsonArray about = new JsonArray();
        ByteBuffer out = ByteBuffer.allocate((int) values * 4);
        try {
            for (DensityFunction f : functions) {
                JsonObject a = new JsonObject();
                Interval range = f.range();
                if (range.isNaI()) {
                    a.add("range", JsonNull.INSTANCE);
                } else {
                    JsonArray r = new JsonArray();
                    r.add(hex(range.min()));
                    r.add(hex(range.max()));
                    a.add("range", r);
                }
                a.addProperty("axes", f.domainAxes());
                about.add(a);
            }
            RandomState state = settings != null
                    ? RandomState.create(noises, seed, settings)
                    : RandomState.create(noises, seed, legacy, Blocks.STONE.defaultBlockState(), 63, zeroRouter());
            List<DensitySampler> samplers = new ArrayList<>();
            for (DensityFunction f : functions) {
                samplers.add(state.getSampler(f));
            }
            SamplerContext context = cached ? SamplerContext.builder().enableCaches().build() : SamplerContext.EMPTY_UNCACHED;
            for (Op op : steps) {
                DensitySampler sampler = samplers.get(op.function);
                if (op.volume == null) {
                    for (int i = 0; i < op.points; i++) {
                        out.putInt(bits(sampler.sampleValue(context, args.getInt(), args.getInt(), args.getInt())));
                    }
                } else {
                    DensityBuffer buffer = DensityBuffer.createUnpooled(op.volume.size());
                    sampler.sampleVolume(context, buffer, op.volume);
                    for (int i = 0; i < buffer.size(); i++) {
                        out.putInt(bits(buffer.get(i)));
                    }
                }
            }
        } catch (CaseError e) {
            throw e;
        } catch (RuntimeException e) {
            return Result.rejected(e);
        }
        JsonObject output = new JsonObject();
        output.add("functions", about);
        return Result.ok(output, out.array());
    }

    private static DensityFunction router(NoiseRouter router, String field, String what) {
        return switch (field) {
            case "temperature" -> router.temperature();
            case "vegetation" -> router.vegetation();
            case "continents" -> router.continents();
            case "erosion" -> router.erosion();
            case "depth" -> router.depth();
            case "ridges" -> router.ridges();
            case "chunk_surface_level" -> router.chunkSurfaceLevel();
            case "final_density" -> router.finalDensity();
            default -> throw new CaseError(what + ": a router has no `" + field + "`, only " + ROUTER);
        };
    }

    private static NoiseRouter zeroRouter() {
        DensityFunction zero = DensityFunctions.zero();
        return new NoiseRouter(zero, zero, zero, zero, zero, zero, zero, zero);
    }

    private static DensityVolume volume(JsonArray v, String what) {
        if (v.size() != 9) {
            throw new CaseError(what + "'s `volume` must have 9 numbers");
        }
        int[] a = new int[9];
        for (int i = 0; i < 9; i++) {
            a[i] = Args.asInt(v.get(i), what + "'s `volume`");
        }
        for (int i : new int[] {0, 1, 2, 6, 7, 8}) {
            if (a[i] <= 0) {
                throw new CaseError(what + "'s `volume` sizes and steps must be positive");
            }
        }
        if ((long) a[0] * a[1] * a[2] > MAX_VOLUME) {
            throw new CaseError(what + "'s `volume` is more than " + MAX_VOLUME + " values");
        }
        return new DensityVolume(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]);
    }

    /** A float's bits, with every NaN the one `Float.floatToIntBits` gives (D198). */
    private static int bits(float value) {
        return Float.floatToIntBits(value);
    }

    private static String hex(float value) {
        return String.format("%08x", bits(value));
    }

    private static boolean bool(JsonObject input, String name) {
        JsonElement value = Args.field(input, name);
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("`" + name + "` must be true or false");
        }
        return value.getAsBoolean();
    }
}
