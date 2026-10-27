package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.util.List;

/** `ping`: echoes its input, for testing the rig itself. */
final class PingProbe implements Probe {
    @Override
    public String name() {
        return "ping";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        JsonObject output = new JsonObject();
        output.add("echo", Args.field(input, "echo"));
        return Result.ok(output, blobs.toArray(byte[][]::new));
    }
}
