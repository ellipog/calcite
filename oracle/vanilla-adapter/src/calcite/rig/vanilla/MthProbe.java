package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.lang.reflect.Field;
import java.nio.ByteBuffer;
import java.util.List;
import net.minecraft.util.Mth;

/** `mth`: vanilla's Mth helpers that use lookup tables or bit tricks. */
final class MthProbe implements Probe {
    @Override
    public String name() {
        return "mth";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) throws ReflectiveOperationException {
        String fn = Args.string(input, "fn");
        return Result.ok(new JsonObject(), switch (fn) {
            case "sin_table" -> {
                if (!blobs.isEmpty()) {
                    throw new CaseError("`sin_table` takes no blobs");
                }
                // Read the table itself, since recomputing an index from an angle can round.
                Field field = Mth.class.getDeclaredField("SIN");
                field.setAccessible(true);
                float[] table = (float[]) field.get(null);
                ByteBuffer out = ByteBuffer.allocate(table.length * 4);
                for (float v : table) {
                    out.putInt(Float.floatToRawIntBits(v));
                }
                yield out.array();
            }
            case "sin", "cos" -> {
                ByteBuffer args = Args.records(blobs, 8);
                ByteBuffer out = ByteBuffer.allocate(args.capacity() / 2);
                while (args.hasRemaining()) {
                    double x = args.getDouble();
                    out.putInt(Float.floatToRawIntBits(fn.equals("sin") ? Mth.sin(x) : Mth.cos(x)));
                }
                yield out.array();
            }
            case "atan2" -> {
                ByteBuffer args = Args.records(blobs, 16);
                ByteBuffer out = ByteBuffer.allocate(args.capacity() / 2);
                while (args.hasRemaining()) {
                    out.putLong(Double.doubleToRawLongBits(Mth.atan2(args.getDouble(), args.getDouble())));
                }
                yield out.array();
            }
            case "fast_inv_sqrt" -> {
                ByteBuffer args = Args.records(blobs, 8);
                ByteBuffer out = ByteBuffer.allocate(args.capacity());
                while (args.hasRemaining()) {
                    out.putLong(Double.doubleToRawLongBits(Mth.fastInvSqrt(args.getDouble())));
                }
                yield out.array();
            }
            case "wrap_degrees" -> {
                ByteBuffer args = Args.records(blobs, 4);
                ByteBuffer out = ByteBuffer.allocate(args.capacity());
                while (args.hasRemaining()) {
                    out.putInt(Float.floatToRawIntBits(Mth.wrapDegrees(args.getFloat())));
                }
                yield out.array();
            }
            case "floor" -> {
                ByteBuffer args = Args.records(blobs, 8);
                ByteBuffer out = ByteBuffer.allocate(args.capacity() / 2);
                while (args.hasRemaining()) {
                    out.putInt(Mth.floor(args.getDouble()));
                }
                yield out.array();
            }
            case "get_seed" -> {
                ByteBuffer args = Args.records(blobs, 12);
                ByteBuffer out = ByteBuffer.allocate(args.capacity() / 12 * 8);
                while (args.hasRemaining()) {
                    out.putLong(Mth.getSeed(args.getInt(), args.getInt(), args.getInt()));
                }
                yield out.array();
            }
            default -> throw new CaseError("unknown function `" + fn + "`");
        });
    }
}
