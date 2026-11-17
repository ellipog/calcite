package calcite.rig.vanilla.agent;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * The entity trace (CAL-159): with {@code trace=PATH}, each living entity's state as the level's
 * tick is done with it, a line each, so a mob's moves can be lined up with Calcite's, which
 * {@code --entity-trace} writes the same way, far finer than its packets show them:
 *
 * <pre>T ID x y z dx dy dz yRot xRot yHeadRot yBodyRot zza xxa speed onGround</pre>
 *
 * <p>with the game time, the entity's ID, its position and motion, its angles, its walk's input
 * and speed, each double and float as Java writes it, the shortest that reads back the same. A
 * player's is written as their own tick, {@code ServerPlayer.doTick}, is done, before
 * {@code tickPlayer} puts them back where their client has them, not as the level ticks them; its
 * body's turn and what they're told to walk as 0, which Calcite doesn't keep. It's loaded the
 * first time {@code ServerLevel.tickNonPassenger} or {@code doTick} calls it, so the game classes
 * it names are loaded by then.
 *
 * <p>With {@code controls} too, each line goes on with a mob's controls (CAL-180):
 *
 * <pre>moveX moveY moveZ moveSpeed moveWanted lookX lookY lookZ looking</pre>
 *
 * <p>its {@code MoveControl}'s wanted place and speed and whether it has one, {@code hasWanted},
 * and its {@code LookControl}'s wanted place and whether it's looking there,
 * {@code isLookingAtTarget}; a living entity that isn't a mob, and a player, writes 0 and false
 * for each.
 */
public final class Trace {
    private static final String NO_CONTROLS = " 0.0 0.0 0.0 0.0 false 0.0 0.0 0.0 false";

    private static Writer out;
    private static boolean controls;

    private Trace() {
    }

    static void start(Path trace, boolean withControls) {
        if (trace == null) {
            return;
        }
        controls = withControls;
        try {
            out = new BufferedWriter(Files.newBufferedWriter(trace, StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            synchronized (Trace.class) {
                try {
                    out.close();
                } catch (IOException ignored) {
                    // The JVM is going; there's nowhere left to say so.
                }
            }
        }, "rig trace"));
    }

    /** The entity the level's tick is done with: written if it's living and not a player. */
    public static void ticked(Object level, Object entity) {
        if (out == null || !(entity instanceof net.minecraft.world.entity.LivingEntity e)
                || entity instanceof net.minecraft.server.level.ServerPlayer) {
            return;
        }
        var at = (net.minecraft.server.level.ServerLevel) level;
        var m = e.getDeltaMovement();
        String line = at.getGameTime() + " " + e.getId() + " " + e.getX() + " " + e.getY() + " " + e.getZ()
                + " " + m.x + " " + m.y + " " + m.z + " " + e.getYRot() + " " + e.getXRot() + " " + e.getYHeadRot()
                + " " + e.yBodyRot + " " + e.zza + " " + e.xxa + " " + e.getSpeed() + " " + e.onGround()
                + controlsOf(e) + "\n";
        write(line);
    }

    /** The mob's controls, as the line goes on with them, or nothing without {@code controls}. */
    private static String controlsOf(net.minecraft.world.entity.LivingEntity e) {
        if (!controls) {
            return "";
        }
        if (!(e instanceof net.minecraft.world.entity.Mob mob)) {
            return NO_CONTROLS;
        }
        var move = mob.getMoveControl();
        var look = mob.getLookControl();
        return " " + move.getWantedX() + " " + move.getWantedY() + " " + move.getWantedZ() + " " + move.getSpeedModifier()
                + " " + move.hasWanted() + " " + look.getWantedX() + " " + look.getWantedY() + " " + look.getWantedZ()
                + " " + look.isLookingAtTarget();
    }

    /** The player whose own tick, {@code doTick}, is done. */
    public static void played(Object player) {
        if (out == null) {
            return;
        }
        var p = (net.minecraft.server.level.ServerPlayer) player;
        var m = p.getDeltaMovement();
        String line = p.level().getGameTime() + " " + p.getId() + " " + p.getX() + " " + p.getY() + " " + p.getZ()
                + " " + m.x + " " + m.y + " " + m.z + " " + p.getYRot() + " " + p.getXRot() + " " + p.getYHeadRot()
                + " 0.0 0.0 0.0 " + p.getSpeed() + " " + p.onGround() + (controls ? NO_CONTROLS : "") + "\n";
        write(line);
    }

    private static void write(String line) {
        synchronized (Trace.class) {
            try {
                out.write(line);
            } catch (IOException ex) {
                throw new UncheckedIOException(ex);
            }
        }
    }
}
