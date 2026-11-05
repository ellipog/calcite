package calcite.rig.vanilla.agent;

import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.levelgen.RandomSupport;

/**
 * What the agent does as each {@code Entity} is made (CAL-148): its random, which vanilla
 * seeds from the clock, is seeded with {@code mixStafford13(seed ^ id)}, as Calcite seeds an
 * entity's with {@code level-random-seed}, and its UUID drawn again from it, as the entity's
 * fields drew it, so an item's UUID, spin and motion are the same on both servers. It's loaded the
 * first time an entity's constructor calls it, so the game classes it names are loaded by then.
 */
public final class Entities {
    private Entities() {
    }

    public static void made(Entity entity) {
        RandomSource random = entity.getRandom();
        random.setSeed(RandomSupport.mixStafford13(Tape.seed() ^ entity.getId()));
        entity.setUUID(Mth.createInsecureUUID(random));
    }
}
