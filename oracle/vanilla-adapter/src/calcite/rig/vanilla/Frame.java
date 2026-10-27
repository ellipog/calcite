package calcite.rig.vanilla;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** One protocol frame: a JSON header and the blobs it lists (rig/PROTOCOL.md, "Frames"). */
record Frame(JsonObject header, List<byte[]> blobs) {
    private static final int MAX_HEADER = 64 << 20;
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().serializeNulls().create();

    /** Reads the next frame, or returns null at the end of the input. */
    static Frame read(DataInputStream in) throws IOException {
        int length;
        try {
            length = in.readInt();
        } catch (EOFException e) {
            return null;
        }
        if (length < 0 || length > MAX_HEADER) {
            throw new IOException("header length " + Integer.toUnsignedString(length) + " is out of range");
        }
        byte[] bytes = in.readNBytes(length);
        if (bytes.length != length) {
            throw new EOFException("header cut short");
        }
        JsonObject header = JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8)).getAsJsonObject();
        List<byte[]> blobs = new ArrayList<>();
        if (header.has("blobs")) {
            for (var size : header.getAsJsonArray("blobs")) {
                long n = size.getAsLong();
                if (n < 0 || n > Integer.MAX_VALUE - 8) {
                    throw new IOException("blob length " + n + " is out of range");
                }
                byte[] blob = in.readNBytes((int) n);
                if (blob.length != n) {
                    throw new EOFException("blob cut short");
                }
                blobs.add(blob);
            }
        }
        return new Frame(header, blobs);
    }

    /** Writes the frame, filling in the header's blob lengths. */
    void write(DataOutputStream out) throws IOException {
        JsonArray sizes = new JsonArray();
        for (byte[] blob : blobs) {
            sizes.add(blob.length);
        }
        header.add("blobs", sizes);
        byte[] bytes = GSON.toJson(header).getBytes(StandardCharsets.UTF_8);
        out.writeInt(bytes.length);
        out.write(bytes);
        for (byte[] blob : blobs) {
            out.write(blob);
        }
        out.flush();
    }
}
