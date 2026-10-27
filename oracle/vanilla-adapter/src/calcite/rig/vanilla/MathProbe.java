package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.nio.ByteBuffer;
import java.util.List;
import java.util.Map;
import java.util.function.DoubleBinaryOperator;
import java.util.function.DoubleUnaryOperator;

/**
 * `math` and `strictmath`: java.lang.Math or StrictMath over a blob of arguments. Vanilla calls
 * Math, so `math` is what Calcite has to match. Comparing the two shows where HotSpot's
 * intrinsics differ from fdlibm (D58).
 */
final class MathProbe implements Probe {
    private static final Map<String, DoubleUnaryOperator> MATH_UNARY = Map.ofEntries(
            Map.entry("sin", Math::sin), Map.entry("cos", Math::cos), Map.entry("tan", Math::tan),
            Map.entry("asin", Math::asin), Map.entry("acos", Math::acos), Map.entry("atan", Math::atan),
            Map.entry("exp", Math::exp), Map.entry("log", Math::log), Map.entry("log10", Math::log10),
            Map.entry("log1p", Math::log1p), Map.entry("expm1", Math::expm1), Map.entry("sqrt", Math::sqrt),
            Map.entry("cbrt", Math::cbrt), Map.entry("sinh", Math::sinh), Map.entry("cosh", Math::cosh),
            Map.entry("tanh", Math::tanh));
    private static final Map<String, DoubleBinaryOperator> MATH_BINARY = Map.of(
            "atan2", Math::atan2, "pow", Math::pow, "hypot", Math::hypot);
    private static final Map<String, DoubleUnaryOperator> STRICT_UNARY = Map.ofEntries(
            Map.entry("sin", StrictMath::sin), Map.entry("cos", StrictMath::cos), Map.entry("tan", StrictMath::tan),
            Map.entry("asin", StrictMath::asin), Map.entry("acos", StrictMath::acos), Map.entry("atan", StrictMath::atan),
            Map.entry("exp", StrictMath::exp), Map.entry("log", StrictMath::log), Map.entry("log10", StrictMath::log10),
            Map.entry("log1p", StrictMath::log1p), Map.entry("expm1", StrictMath::expm1), Map.entry("sqrt", StrictMath::sqrt),
            Map.entry("cbrt", StrictMath::cbrt), Map.entry("sinh", StrictMath::sinh), Map.entry("cosh", StrictMath::cosh),
            Map.entry("tanh", StrictMath::tanh));
    private static final Map<String, DoubleBinaryOperator> STRICT_BINARY = Map.of(
            "atan2", StrictMath::atan2, "pow", StrictMath::pow, "hypot", StrictMath::hypot);

    private final String name;
    private final Map<String, DoubleUnaryOperator> unary;
    private final Map<String, DoubleBinaryOperator> binary;

    MathProbe(String name) {
        this.name = name;
        boolean strict = name.equals("strictmath");
        this.unary = strict ? STRICT_UNARY : MATH_UNARY;
        this.binary = strict ? STRICT_BINARY : MATH_BINARY;
    }

    @Override
    public String name() {
        return name;
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        String fn = Args.string(input, "fn");
        DoubleUnaryOperator f1 = unary.get(fn);
        DoubleBinaryOperator f2 = binary.get(fn);
        if (f1 == null && f2 == null) {
            throw new CaseError("unknown function `" + fn + "`");
        }
        ByteBuffer args = Args.records(blobs, f1 != null ? 8 : 16);
        ByteBuffer out = ByteBuffer.allocate(f1 != null ? args.capacity() : args.capacity() / 2);
        while (args.hasRemaining()) {
            double r = f1 != null ? f1.applyAsDouble(args.getDouble()) : f2.applyAsDouble(args.getDouble(), args.getDouble());
            out.putLong(Double.doubleToRawLongBits(r));
        }
        return Result.ok(new JsonObject(), out.array());
    }
}
