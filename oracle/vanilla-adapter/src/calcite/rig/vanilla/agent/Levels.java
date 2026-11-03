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
        level.getRandom().setSeed(RandomSupport.mixStafford13(Tape.seed() ^ name.hashCode()));
        Tape.watch(level.getRandom(), name, level::getGameTime);
    }

    /**
     * As {@code level}'s tick starts: the first time it's at the reseed time or later, its random
     * is seeded again as {@link #made} seeded it, so the two servers' draws line up again from
     * there, whatever each drew before (D316).
     */
    public static void ticking(ServerLevel level) {
        if (reseedAt < 0 || level.getGameTime() < reseedAt) {
            return;
        }
        String name = level.dimension().identifier().toString();
        if (reseeded.add(name)) {
            level.getRandom().setSeed(RandomSupport.mixStafford13(Tape.seed() ^ name.hashCode()));
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
