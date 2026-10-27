package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.List;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.LegacyRandomSource;
import net.minecraft.world.level.levelgen.SingleThreadedRandomSource;
import net.minecraft.world.level.levelgen.WorldgenRandom;
import net.minecraft.world.level.levelgen.XoroshiroRandomSource;

/** `rng`: a sequence of operations on one of vanilla's random sources. */
final class RngProbe implements Probe {
    @Override
    public String name() {
        return "rng";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws IOException {
        RandomSource source = create(input);
        JsonArray ops = Args.array(input, "ops");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        for (int i = 0; i < ops.size(); i++) {
            if (!ops.get(i).isJsonArray() || ops.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError("operation " + i + " must be a non-empty array");
            }
            try {
                source = apply(source, new Op(ops.get(i).getAsJsonArray(), i), out);
            } catch (CaseError e) {
                throw e;
            } catch (RuntimeException e) {
                // The game threw, such as nextInt(0). Stop here, keeping what came before.
                JsonObject output = Result.rejection(e);
                output.addProperty("at", i);
                return Result.ok(output, bytes.toByteArray());
            }
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    private static RandomSource create(JsonObject input) {
        String kind = Args.string(input, "kind");
        return switch (kind) {
            case "legacy" -> new LegacyRandomSource(Args.int64(input, "seed"));
            case "single_threaded" -> new SingleThreadedRandomSource(Args.int64(input, "seed"));
            case "xoroshiro" -> new XoroshiroRandomSource(Args.int64(input, "seed"));
            case "xoroshiro128" -> new XoroshiroRandomSource(Args.int64(input, "seed_lo"), Args.int64(input, "seed_hi"));
            case "worldgen_legacy" -> new WorldgenRandom(new LegacyRandomSource(Args.int64(input, "seed")));
            case "worldgen_xoroshiro" -> new WorldgenRandom(new XoroshiroRandomSource(Args.int64(input, "seed")));
            default -> throw new CaseError("unknown kind `" + kind + "`");
        };
    }

    /** Applies one operation, writing its result, and returns the source to continue with. */
    private static RandomSource apply(RandomSource r, Op op, DataOutputStream out) throws IOException {
        switch (op.name) {
            case "nextInt" -> {
                if (op.arity() == 0) {
                    out.writeInt(r.nextInt());
                } else {
                    op.expect(1);
                    out.writeInt(r.nextInt(op.i(1)));
                }
            }
            case "nextIntRange" -> {
                op.expect(2);
                out.writeInt(r.nextInt(op.i(1), op.i(2)));
            }
            case "nextIntBetween" -> {
                op.expect(2);
                out.writeInt(r.nextIntBetweenInclusive(op.i(1), op.i(2)));
            }
            case "nextLong" -> {
                op.expect(0);
                out.writeLong(r.nextLong());
            }
            case "nextBoolean" -> {
                op.expect(0);
                out.writeBoolean(r.nextBoolean());
            }
            case "nextFloat" -> {
                op.expect(0);
                out.writeInt(Float.floatToRawIntBits(r.nextFloat()));
            }
            case "nextDouble" -> {
                op.expect(0);
                out.writeLong(Double.doubleToRawLongBits(r.nextDouble()));
            }
            case "nextGaussian" -> {
                op.expect(0);
                out.writeLong(Double.doubleToRawLongBits(r.nextGaussian()));
            }
            case "triangle" -> {
                op.expect(2);
                out.writeLong(Double.doubleToRawLongBits(r.triangle(op.d(1), op.d(2))));
            }
            case "setSeed" -> {
                op.expect(1);
                r.setSeed(op.l(1));
            }
            case "consume" -> {
                op.expect(1);
                r.consumeCount(op.i(1));
            }
            case "fork" -> {
                op.expect(0);
                return r.fork();
            }
            case "at" -> {
                op.expect(3);
                return r.forkPositional().at(op.i(1), op.i(2), op.i(3));
            }
            case "fromHashOf" -> {
                op.expect(1);
                return r.forkPositional().fromHashOf(op.s(1));
            }
            case "fromSeed" -> {
                op.expect(1);
                return r.forkPositional().fromSeed(op.l(1));
            }
            case "setDecorationSeed" -> {
                op.expect(3);
                out.writeLong(worldgen(r, op).setDecorationSeed(op.l(1), op.i(2), op.i(3)));
            }
            case "setFeatureSeed" -> {
                op.expect(3);
                worldgen(r, op).setFeatureSeed(op.l(1), op.i(2), op.i(3));
            }
            case "setLargeFeatureSeed" -> {
                op.expect(3);
                worldgen(r, op).setLargeFeatureSeed(op.l(1), op.i(2), op.i(3));
            }
            case "setLargeFeatureWithSalt" -> {
                op.expect(4);
                worldgen(r, op).setLargeFeatureWithSalt(op.l(1), op.i(2), op.i(3), op.i(4));
            }
            default -> throw new CaseError("operation " + op.index + ": unknown `" + op.name + "`");
        }
        return r;
    }

    private static WorldgenRandom worldgen(RandomSource r, Op op) {
        if (r instanceof WorldgenRandom w) {
            return w;
        }
        throw new CaseError("operation " + op.index + ": `" + op.name + "` needs a worldgen source");
    }

    /** One operation from the case, with its arguments checked as they're read. */
    private static final class Op {
        final JsonArray items;
        final int index;
        final String name;

        Op(JsonArray items, int index) {
            this.items = items;
            this.index = index;
            this.name = Args.asString(items.get(0), "operation " + index + "'s name");
        }

        int arity() {
            return items.size() - 1;
        }

        void expect(int arity) {
            if (arity() != arity) {
                throw new CaseError("operation " + index + ": `" + name + "` takes " + arity + " arguments, got " + arity());
            }
        }

        private String what(int i) {
            return "operation " + index + " argument " + i;
        }

        int i(int i) {
            return Args.asInt(items.get(i), what(i));
        }

        long l(int i) {
            return Args.parseLong(Args.asString(items.get(i), what(i)), what(i));
        }

        double d(int i) {
            return Args.parseDouble(Args.asString(items.get(i), what(i)), what(i));
        }

        String s(int i) {
            return Args.asString(items.get(i), what(i));
        }
    }
}
