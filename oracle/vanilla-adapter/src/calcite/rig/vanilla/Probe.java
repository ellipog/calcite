package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.util.List;

/** A probe: a pure function from a case's input to vanilla's result (rig/PROTOCOL.md, "Probes"). */
interface Probe {
    String name();

    int version();

    /**
     * Runs one case. Throws {@link CaseError} if the case itself is malformed. Anything the game
     * rejects is an ordinary result, built with {@link Result#rejected}.
     */
    Result run(JsonObject input, List<byte[]> blobs) throws Exception;
}
