package calcite.rig.vanilla.agent;

import java.lang.reflect.Field;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.levelgen.RandomSupport;

/**
 * What the agent does as each {@code ServerLevel} is made (D311). It's loaded the first time a
 * level's constructor calls it, so the game classes it names are loaded by then.
 */
public final class Levels {
    // The game time from which each level's random is seeded again, or -1 for never, and the
    // levels whose have been.
    private static long reseedAt = -1;
    private static final Set<String> reseeded = new HashSet<>();

    private Levels() {
    }

    static void reseedAt(long time) {
        reseedAt = time;
    }

    /**
     * Seeds {@code level}'s random with {@code mixStafford13(seed ^ name.hashCode())}, as
     * Calcite's {@code level-random-seed} seeds its own, puts it on the tape, and, for the
     * Overworld, the first level made, sets the entity counter back to 0, so the first entity is
     * 1 whatever came before in the process.
     */
    public static void made(ServerLevel level) {
        String name = level.dimension().identifier().toString();
        if (level.dimension() == Level.OVERWORLD) {
            counter().set(0);
        }
        seed(level, name);
        Tape.watch(level.getRandom(), name, level::getGameTime);
    }

    /**
     * Seeds {@code level}'s random, and sets the value {@code getBlockRandomPos} steps, which
     * picks where random ticks and precipitation land, to the seed's low 32 bits, where vanilla
     * starts it from a random of the thread's own (D318).
     */
    private static void seed(ServerLevel level, String name) {
        long seed = RandomSupport.mixStafford13(Tape.seed() ^ name.hashCode());
        level.getRandom().setSeed(seed);
        try {
            Field f = Level.class.getDeclaredField("randValue");
            f.setAccessible(true);
            f.setInt(level, (int) seed);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("agent: Level has no randValue", e);
        }
    }

    /**
     * As {@code level}'s tick starts: the first time it's at the reseed time or later, its random
     * is seeded again as {@link #made} seeded it, with its {@code randValue}, so the two servers'
     * draws line up again from there, whatever each drew before (D316, D318).
     */
    public static void ticking(ServerLevel level) {
        if (reseedAt < 0 || level.getGameTime() < reseedAt) {
            return;
        }
        String name = level.dimension().identifier().toString();
        if (reseeded.add(name)) {
            seed(level, name);
        }
    }

    private static AtomicInteger counter() {
        try {
            Field f = ServerLevel.class.getDeclaredField("ENTITY_COUNTER");
            f.setAccessible(true);
            return (AtomicInteger) f.get(null);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("agent: ServerLevel has no ENTITY_COUNTER", e);
        }
    }
}
