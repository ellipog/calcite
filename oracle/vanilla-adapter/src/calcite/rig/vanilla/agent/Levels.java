package calcite.rig.vanilla.agent;

import java.lang.reflect.Field;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.levelgen.RandomSupport;

/**
 * What the agent does as each {@code ServerLevel} is made (D311). It's loaded the first time a
 * level's constructor calls it, so the game classes it names are loaded by then.
 */
public final class Levels {
    private Levels() {
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
