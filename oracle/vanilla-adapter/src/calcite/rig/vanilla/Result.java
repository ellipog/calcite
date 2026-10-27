package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.util.List;

/** What a probe returns: the `status`, `output` and blobs of a `result` message. */
record Result(String status, JsonObject output, List<byte[]> blobs, String message) {
    static Result ok(JsonObject output, byte[]... blobs) {
        return new Result("ok", output, List.of(blobs), null);
    }

    static Result unimplemented(String message) {
        return new Result("unimplemented", new JsonObject(), List.of(), message);
    }

    /**
     * The game rejected the input. That's still an `ok` result: the exception's simple class name
     * and message are the output, so the rejection is compared like any other result.
     */
    static Result rejected(Throwable e, byte[]... blobs) {
        return ok(rejection(e), blobs);
    }

    static JsonObject rejection(Throwable e) {
        JsonObject output = new JsonObject();
        output.addProperty("exception", e.getClass().getSimpleName());
        output.addProperty("error", e.getMessage() == null ? "" : e.getMessage());
        return output;
    }
}
