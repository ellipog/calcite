package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import java.nio.ByteBuffer;
import java.util.List;
import net.minecraft.util.Interval;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.LegacyRandomSource;
import net.minecraft.world.level.levelgen.XoroshiroRandomSource;
import net.minecraft.world.level.levelgen.densityfunction.DensityBuffer;
import net.minecraft.world.level.levelgen.densityfunction.DensityVolume;
import net.minecraft.world.level.levelgen.synth.BlendedNoise;
import net.minecraft.world.level.levelgen.synth.Noise;
import net.minecraft.world.level.levelgen.synth.NormalNoise;
import net.minecraft.world.level.levelgen.synth.PerlinNoise;
import net.minecraft.world.level.levelgen.synth.SimplexNoise;
import net.minecraft.world.level.levelgen.synth.SmearedPerlinNoise;

/** `noise`: vanilla's noises, sampled at points or over a volume. */
final class NoiseProbe implements Probe {
    private static final int MAX_VOLUME = 65536;

    @Override
    public String name() {
        return "noise";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        RandomSource random = random(input);
        JsonElement spec = Args.field(input, "noise");
        if (!spec.isJsonObject()) {
            throw new CaseError("`noise` must be an object");
        }
        JsonObject n = spec.getAsJsonObject();
        String type = Args.string(n, "type");
        NormalNoise normal = null;
        if (type.equals("normal") || type.equals("legacy_nether")) {
            normal = NormalNoise.DIRECT_CODEC.parse(JsonOps.INSTANCE, Args.field(n, "parameters"))
                    .getOrThrow(message -> new CaseError("`parameters`: " + message));
        }
        String fn = Args.string(input, "fn");
        // Check the case before making the noise, so that a bad case is an error and not a
        // rejection.
        Volume volume = fn.equals("volume") ? volume(input, blobs) : null;
        Noise noise;
        try {
            noise = switch (type) {
                case "perlin" -> new PerlinNoise(random);
                case "smeared" -> new SmearedPerlinNoise(random, decimal(n, "fudge_y_scale"));
                case "simplex" -> new SimplexNoise(random, bool(n, "discard_offset"));
                case "normal" -> normal.create(random);
                case "legacy_nether" -> normal.createForLegacyNetherBiome(random);
                case "fbm" -> BlendedNoise.createFbm(
                        random, Args.asInt(Args.field(n, "first_octave"), "`first_octave`"),
                        decimal(n, "smear_scale_y"), decimal(n, "value_factor"));
                default -> throw new CaseError("unknown noise `" + type + "`");
            };
        } catch (CaseError e) {
            throw e;
        } catch (RuntimeException e) {
            return Result.rejected(e);
        }
        return Result.ok(new JsonObject(), switch (fn) {
            case "get3" -> {
                ByteBuffer args = Args.records(blobs, 24);
                ByteBuffer out = ByteBuffer.allocate(args.capacity() / 6);
                while (args.hasRemaining()) {
                    out.putInt(bits(noise.get(args.getDouble(), args.getDouble(), args.getDouble())));
                }
                yield out.array();
            }
            case "get2" -> {
                ByteBuffer args = Args.records(blobs, 16);
                ByteBuffer out = ByteBuffer.allocate(args.capacity() / 4);
                while (args.hasRemaining()) {
                    out.putInt(bits(noise.get(args.getDouble(), args.getDouble())));
                }
                yield out.array();
            }
            case "volume" -> {
                DensityBuffer buffer = DensityBuffer.createUnpooled(volume.volume.size());
                noise.addToVolume(buffer, volume.volume, volume.xzScale, volume.yScale, volume.amplitude);
                ByteBuffer out = ByteBuffer.allocate(buffer.size() * 4);
                for (int i = 0; i < buffer.size(); i++) {
                    out.putInt(bits(buffer.get(i)));
                }
                yield out.array();
            }
            case "range" -> {
                if (!blobs.isEmpty()) {
                    throw new CaseError("`range` takes no blobs");
                }
                ByteBuffer out = ByteBuffer.allocate(normal == null ? 8 : 16);
                put(out, noise.range());
                if (normal != null) {
                    put(out, normal.range());
                }
                yield out.array();
            }
            default -> throw new CaseError("unknown fn `" + fn + "`");
        });
    }

    private record Volume(DensityVolume volume, double xzScale, double yScale, float amplitude) {}

    private static Volume volume(JsonObject input, List<byte[]> blobs) {
        if (!blobs.isEmpty()) {
            throw new CaseError("`volume` takes no blobs");
        }
        JsonArray v = Args.array(input, "volume");
        if (v.size() != 9) {
            throw new CaseError("`volume` must have 9 numbers");
        }
        int[] a = new int[9];
        for (int i = 0; i < 9; i++) {
            a[i] = Args.asInt(v.get(i), "`volume`");
        }
        for (int i : new int[] {0, 1, 2, 6, 7, 8}) {
            if (a[i] <= 0) {
                throw new CaseError("`volume`'s sizes and steps must be positive");
            }
        }
        if ((long) a[0] * a[1] * a[2] > MAX_VOLUME) {
            throw new CaseError("`volume` is more than " + MAX_VOLUME + " values");
        }
        return new Volume(
                new DensityVolume(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]),
                decimal(input, "xz_scale"),
                decimal(input, "y_scale"),
                single(input, "amplitude"));
    }

    private static RandomSource random(JsonObject input) {
        String kind = Args.string(input, "random");
        long seed = Args.int64(input, "seed");
        return switch (kind) {
            case "legacy" -> new LegacyRandomSource(seed);
            case "xoroshiro" -> new XoroshiroRandomSource(seed);
            default -> throw new CaseError("unknown random `" + kind + "`");
        };
    }

    private static void put(ByteBuffer out, Interval range) {
        out.putInt(bits(range.min()));
        out.putInt(bits(range.max()));
    }

    /**
     * A float's bits, with every NaN the one NaN `Float.floatToIntBits` gives (D198). Java doesn't
     * say which NaN an operation on two NaNs gives, and on x86 it's the one the JIT puts first.
     */
    private static int bits(float value) {
        return Float.floatToIntBits(value);
    }

    private static double decimal(JsonObject input, String name) {
        return Args.parseDouble(Args.string(input, name), "`" + name + "`");
    }

    private static float single(JsonObject input, String name) {
        String text = Args.string(input, name);
        try {
            return Float.parseFloat(text);
        } catch (NumberFormatException e) {
            throw new CaseError("`" + name + "` must be a decimal number");
        }
    }

    private static boolean bool(JsonObject input, String name) {
        JsonElement value = Args.field(input, name);
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("`" + name + "` must be true or false");
        }
        return value.getAsBoolean();
    }
}
