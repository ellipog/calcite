package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.nio.ByteBuffer;
import java.util.List;

/**
 * Reads case inputs. Every failure is a {@link CaseError}, so any other exception a probe sees
 * came from the game.
 */
final class Args {
    private Args() {}

    static JsonElement field(JsonObject input, String name) {
        JsonElement value = input.get(name);
        if (value == null) {
            throw new CaseError("missing field `" + name + "`");
        }
        return value;
    }

    static String string(JsonObject input, String name) {
        return asString(field(input, name), "`" + name + "`");
    }

    static JsonArray array(JsonObject input, String name) {
        JsonElement value = field(input, name);
        if (!value.isJsonArray()) {
            throw new CaseError("`" + name + "` must be an array");
        }
        return value.getAsJsonArray();
    }

    /** A 64-bit value, which the protocol writes as a decimal string. */
    static long int64(JsonObject input, String name) {
        return parseLong(string(input, name), "`" + name + "`");
    }

    static String asString(JsonElement value, String what) {
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isString()) {
            throw new CaseError(what + " must be a string");
        }
        return value.getAsString();
    }

    static int asInt(JsonElement value, String what) {
        if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isNumber()) {
            throw new CaseError(what + " must be a number");
        }
        try {
            return value.getAsBigDecimal().intValueExact();
        } catch (ArithmeticException e) {
            throw new CaseError(what + " must be a 32-bit integer");
        }
    }

    static long parseLong(String text, String what) {
        try {
            return Long.parseLong(text);
        } catch (NumberFormatException e) {
            throw new CaseError(what + " must be a decimal 64-bit integer");
        }
    }

    static double parseDouble(String text, String what) {
        try {
            return Double.parseDouble(text);
        } catch (NumberFormatException e) {
            throw new CaseError(what + " must be a decimal number");
        }
    }

    static byte[] oneBlob(List<byte[]> blobs) {
        if (blobs.size() != 1) {
            throw new CaseError("expected exactly one blob, got " + blobs.size());
        }
        return blobs.get(0);
    }

    /** One blob of fixed-size records, big-endian. */
    static ByteBuffer records(List<byte[]> blobs, int recordSize) {
        byte[] blob = oneBlob(blobs);
        if (blob.length % recordSize != 0) {
            throw new CaseError("blob length " + blob.length + " isn't a multiple of " + recordSize);
        }
        return ByteBuffer.wrap(blob);
    }
}
