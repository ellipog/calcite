package calcite.rig.vanilla;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FileDescriptor;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;

/** The vanilla adapter: answers the rig's requests over stdin and stdout (rig/PROTOCOL.md). */
public final class Main {
    static final int PROTOCOL = 1;

    private Main() {}

    public static void main(String[] args) throws IOException {
        // Stdout carries only frames. Take the real stream before anything can print to it, and
        // point System.out at stderr so a stray print from the game lands in the log instead.
        DataOutputStream out = new DataOutputStream(new BufferedOutputStream(new FileOutputStream(FileDescriptor.out), 1 << 16));
        System.setOut(System.err);
        DataInputStream in = new DataInputStream(new BufferedInputStream(new FileInputStream(FileDescriptor.in), 1 << 16));

        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();

        Map<String, Probe> probes = new LinkedHashMap<>();
        for (Probe probe : List.of(
                new PingProbe(),
                new RngProbe(),
                new NbtProbe(),
                new TextProbe(),
                new MathProbe("math"),
                new MathProbe("strictmath"),
                new MthProbe(),
                new BlockStateProbe(),
                new CollectionsProbe(),
                new PaletteProbe(),
                new RegistriesProbe())) {
            probes.put(probe.name(), probe);
        }

        Frame request;
        while ((request = Frame.read(in)) != null) {
            JsonObject header = request.header();
            String type = header.has("type") ? header.get("type").getAsString() : "";
            switch (type) {
                case "hello" -> hello(probes).write(out);
                case "run" -> run(probes, header, request.blobs()).write(out);
                case "bye" -> {
                    JsonObject bye = new JsonObject();
                    bye.addProperty("type", "bye");
                    new Frame(bye, List.of()).write(out);
                    System.exit(0);
                }
                default -> response(header.get("id"), new Result("error", new JsonObject(), List.of(), "unknown message type `" + type + "`")).write(out);
            }
        }
        // The runner closed our input without saying bye.
        System.exit(1);
    }

    private static Frame hello(Map<String, Probe> probes) {
        JsonObject hello = new JsonObject();
        hello.addProperty("type", "hello");
        hello.addProperty("protocol", PROTOCOL);
        hello.addProperty("adapter", "vanilla");
        hello.addProperty("game_version", SharedConstants.getCurrentVersion().name());
        JsonObject list = new JsonObject();
        for (Probe probe : probes.values()) {
            list.addProperty(probe.name(), probe.version());
        }
        hello.add("probes", list);
        JsonObject about = new JsonObject();
        for (String key : List.of("java.vm.name", "java.vm.version", "os.name", "os.arch")) {
            about.addProperty(key, System.getProperty(key));
        }
        hello.add("about", about);
        return new Frame(hello, List.of());
    }

    private static Frame run(Map<String, Probe> probes, JsonObject header, List<byte[]> blobs) {
        JsonElement id = header.get("id");
        String name = header.has("probe") ? header.get("probe").getAsString() : "";
        Probe probe = probes.get(name);
        if (probe == null) {
            return response(id, Result.unimplemented("no probe `" + name + "`"));
        }
        JsonObject input = header.has("input") && header.get("input").isJsonObject()
                ? header.getAsJsonObject("input")
                : new JsonObject();
        Result result;
        try {
            result = probe.run(input, blobs);
        } catch (CaseError e) {
            result = new Result("error", new JsonObject(), List.of(), "bad case: " + e.getMessage());
        } catch (Throwable e) {
            StringWriter trace = new StringWriter();
            e.printStackTrace(new PrintWriter(trace));
            result = new Result("error", new JsonObject(), List.of(), trace.toString());
        }
        return response(id, result);
    }

    private static Frame response(JsonElement id, Result result) {
        JsonObject header = new JsonObject();
        header.addProperty("type", "result");
        header.add("id", id);
        header.addProperty("status", result.status());
        header.add("output", result.output());
        if (result.message() != null) {
            header.addProperty("message", result.message());
        }
        return new Frame(header, result.blobs());
    }
}
