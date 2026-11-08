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
 *
 * <p>And as a brain's made for an entity, {@code Brain.Provider.makeBrain} (CAL-160): each
 * {@code ShufflingList} its behaviors make, a {@code RunOne}'s or another {@code GateBehavior}'s,
 * whose random vanilla makes unseeded, {@code RandomSource.create}, is seeded with
 * {@code mixStafford13(mixStafford13(seed ^ id) + k + 1)}, {@code k} counting the brain's lists
 * from 0 in the order they're made, as Calcite seeds its gates' from the entity's seed. Lists made
 * outside a brain keep vanilla's unseeded random.
 */
public final class Entities {
    private static final ThreadLocal<Entity> BRAINING = new ThreadLocal<>();
    private static final ThreadLocal<int[]> LISTS = ThreadLocal.withInitial(() -> new int[1]);

    private Entities() {
    }

    public static void made(Entity entity) {
        RandomSource random = entity.getRandom();
        random.setSeed(RandomSupport.mixStafford13(Tape.seed() ^ entity.getId()));
        entity.setUUID(Mth.createInsecureUUID(random));
    }

    // A brain's being made for the entity `body`, its lists counted from 0.
    public static void braining(Object body) {
        BRAINING.set((Entity) body);
        LISTS.get()[0] = 0;
    }

    // The brain's made.
    public static void brained() {
        BRAINING.remove();
    }

    // A ShufflingList's made, `random` its own.
    public static void shuffling(Object random) {
        Entity body = BRAINING.get();
        if (body == null) {
            return;
        }
        int k = LISTS.get()[0]++;
        long own = RandomSupport.mixStafford13(Tape.seed() ^ body.getId());
        ((RandomSource) random).setSeed(RandomSupport.mixStafford13(own + k + 1));
    }
}
