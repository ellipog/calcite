package calcite.rig.vanilla.agent;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.function.LongSupplier;

/**
 * The RNG tape (P6.1, D311): each value a level's random draws, a line each, with the level, its
 * game time, the bits drawn, the value, and where it was drawn: the first two frames of the
 * stack outside the random classes, the method that asked for it and what called that.
 *
 * <pre>minecraft:overworld 0 31 1424587364 ServerLevel.advanceWeatherCycle:1012 ServerLevel.tick:420</pre>
 *
 * <p>{@code LegacyRandomSource.next} calls {@link #drew} for every value it returns, so it must be
 * cheap for the randoms that aren't a level's: one comparison for each level. It names no game
 * class, since it may be loaded by the first draw of any random, before any level is made.
 */
public final class Tape {
    private record Watched(Object random, String name, LongSupplier time) {
    }

    // What's skipped to find where a value was asked for: the agent and the random classes.
    private static final Set<String> RANDOM = Set.of(
            "calcite.rig.vanilla.agent.Tape",
            "net.minecraft.world.level.levelgen.LegacyRandomSource",
            "net.minecraft.world.level.levelgen.BitRandomSource",
            "net.minecraft.world.level.levelgen.MarsagliaPolarGaussian",
            "net.minecraft.util.RandomSource");
    private static final StackWalker WALKER = StackWalker.getInstance();

    private static long seed;
    private static Writer out;
    private static volatile Watched[] watched = new Watched[0];

    private Tape() {
    }

    static void start(long base, Path tape) {
        seed = base;
        if (tape == null) {
            return;
        }
        try {
            out = new BufferedWriter(Files.newBufferedWriter(tape, StandardCharsets.UTF_8));
            out.write("# seed " + base + "\n");
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            synchronized (Tape.class) {
                try {
                    out.close();
                } catch (IOException ignored) {
                    // The JVM is going; there's nowhere left to say so.
                }
            }
        }, "rig tape"));
    }

    /** The seed the agent was started with. */
    static long seed() {
        return seed;
    }

    /** Puts {@code random}, the level {@code name}'s, on the tape, with its game time. */
    static synchronized void watch(Object random, String name, LongSupplier time) {
        Watched[] grown = Arrays.copyOf(watched, watched.length + 1);
        grown[grown.length - 1] = new Watched(random, name, time);
        watched = grown;
    }

    /** {@code value}, the {@code bits} bits {@code source} drew: written if it's a level's. */
    public static void drew(int value, Object source, int bits) {
        if (out == null) {
            return;
        }
        for (Watched w : watched) {
            if (w.random == source) {
                write(w, bits, value);
                return;
            }
        }
    }

    private static void write(Watched w, int bits, int value) {
        List<String> site = WALKER.walk(s -> s.filter(f -> !RANDOM.contains(f.getClassName())).limit(2)
                .map(f -> simple(f.getClassName()) + "." + f.getMethodName() + ":" + f.getLineNumber()).toList());
        String line = w.name + " " + w.time.getAsLong() + " " + bits + " " + value + " " + String.join(" ", site) + "\n";
        synchronized (Tape.class) {
            try {
                out.write(line);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
    }

    private static String simple(String name) {
        return name.substring(name.lastIndexOf('.') + 1);
    }
}
