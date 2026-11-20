package calcite.rig.vanilla.agent;

import java.lang.reflect.Field;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.gamerules.GameRules;
import net.minecraft.world.level.levelgen.RandomSupport;

/**
 * What the agent does as each {@code ServerLevel} is made (D311). It's loaded the first time a
 * level's constructor calls it, so the game classes it names are loaded by then.
 */
public final class Levels {
    // The game time from which each level's random is seeded again, or -1 for never, those of the
    // levels seeded again from times of their own, by their dimensions' names (CAL-167), and the
    // levels whose have been.
    private static long reseedAt = -1;
    private static final Map<String, Long> reseedIn = new HashMap<>();
    private static final Set<String> reseeded = new HashSet<>();
    // The random tick speed set as the first level's seeded again, or -1 for none (CAL-301).
    private static int ticksAfter = -1;
    // ChunkMap's level, which saveMillis reads the game time of.
    private static Field chunkLevel;

    private Levels() {
    }

    static void reseedAt(long time) {
        reseedAt = time;
    }

    static void reseedAt(String name, long time) {
        reseedIn.put(name, time);
    }

    static void ticksAfter(int speed) {
        ticksAfter = speed;
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
        if (reseedAt < 0) {
            return;
        }
        String name = level.dimension().identifier().toString();
        if (level.getGameTime() < reseedIn.getOrDefault(name, reseedAt)) {
            return;
        }
        if (reseeded.add(name)) {
            seed(level, name);
            // Random ticks on from here, at the speed the rig wants, where they were off till
            // the randoms line up, as they'd change blocks at times that differ from run to run
            // (CAL-301); set once, by the first level seeded again, as the rule's the server's.
            if (ticksAfter >= 0 && level.getGameRules().get(GameRules.RANDOM_TICK_SPEED) != ticksAfter) {
                level.getGameRules().set(GameRules.RANDOM_TICK_SPEED, ticksAfter, level.getServer());
            }
        }
    }

    /**
     * The random a dragon fight's respawn builds a spike again with, which turns its new crystal,
     * where vanilla makes it unseeded, {@code RandomSource.create()} (CAL-167): seeded with
     * {@code mixStafford13(seed ^ time)}, {@code time} the level's game time, as Calcite's
     * {@code level-random-seed} seeds its own.
     */
    public static RandomSource pillars(Object level) {
        return RandomSource.create(RandomSupport.mixStafford13(Tape.seed() ^ ((ServerLevel) level).getGameTime()));
    }

    /**
     * The clock {@code ChunkMap} saves chunks by, where vanilla's is the wall clock's,
     * {@code Util.getMillis()} (CAL-261): the game time of the map's level, 50 a tick, so a
     * chunk's saved 200 ticks at the soonest after it last was, as Calcite's are in the rig.
     */
    public static long saveMillis(Object map) {
        try {
            if (chunkLevel == null) {
                Field f = map.getClass().getDeclaredField("level");
                f.setAccessible(true);
                chunkLevel = f;
            }
            return ((ServerLevel) chunkLevel.get(map)).getGameTime() * 50;
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("agent: ChunkMap has no level", e);
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
