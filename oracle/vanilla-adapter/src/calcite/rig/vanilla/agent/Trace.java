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
 * <pre>moveX moveY moveZ moveSpeed moveWanted lookX lookY lookZ looking seed</pre>
 *
 * <p>its {@code MoveControl}'s wanted place and speed and whether it has one, {@code hasWanted},
 * and its {@code LookControl}'s wanted place and whether it's looking there,
 * {@code isLookingAtTarget}, and its own random's seed as it is now, so where a mob's draws part
 * shows (CAL-303); a living entity that isn't a mob, and a player, writes 0 and false for each.
 *
 * <p>With {@code controls}, {@code paths.txt} beside the trace gets a line each time a mob's
 * navigation's path is another than as its last tick was done, or it's moved on to another node of
 * it (CAL-403):
 *
 * <pre>T ID next tx,ty,tz x,y,z...</pre>
 *
 * <p>the game time, the mob's ID, the index of the node it's going to, the path's target and its
 * nodes in order, or {@code T ID none} where it has none.
 */
public final class Trace {
    private static final String NO_CONTROLS = " 0.0 0.0 0.0 0.0 false 0.0 0.0 0.0 false 0";

    private static Writer out;
    private static Writer paths;
    private static boolean controls;
    /** Each mob's path as it was last written, by ID: its identity and its next node's index. */
    private static final java.util.Map<Integer, String> lastPaths = new java.util.HashMap<>();

    private Trace() {
    }

    static void start(Path trace, boolean withControls) {
        if (trace == null) {
            return;
        }
        controls = withControls;
        try {
            out = new BufferedWriter(Files.newBufferedWriter(trace, StandardCharsets.UTF_8));
            if (withControls) {
                paths = new BufferedWriter(Files.newBufferedWriter(trace.resolveSibling("paths.txt"), StandardCharsets.UTF_8));
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            synchronized (Trace.class) {
                try {
                    out.close();
                    if (paths != null) {
                        paths.close();
                    }
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
        if (controls && e instanceof net.minecraft.world.entity.Mob mob) {
            pathOf(at.getGameTime(), mob);
        }
    }

    /** The mob's path, written to {@code paths.txt} where it isn't as it was last written. */
    private static void pathOf(long time, net.minecraft.world.entity.Mob mob) {
        var path = mob.getNavigation().getPath();
        String key = path == null ? "none" : System.identityHashCode(path) + ":" + path.getNextNodeIndex();
        if (key.equals(lastPaths.get(mob.getId()))) {
            return;
        }
        lastPaths.put(mob.getId(), key);
        StringBuilder b = new StringBuilder();
        b.append(time).append(' ').append(mob.getId()).append(' ');
        if (path == null) {
            b.append("none");
        } else {
            var target = path.getTarget();
            b.append(path.getNextNodeIndex()).append(' ').append(target.getX()).append(',').append(target.getY()).append(',').append(target.getZ());
            for (int i = 0; i < path.getNodeCount(); i++) {
                var node = path.getNode(i);
                b.append(' ').append(node.x).append(',').append(node.y).append(',').append(node.z);
            }
        }
        b.append('\n');
        synchronized (Trace.class) {
            try {
                paths.write(b.toString());
            } catch (IOException ex) {
                throw new UncheckedIOException(ex);
            }
        }
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
                + " " + look.isLookingAtTarget() + " " + seedOf(mob);
    }

    /** The seed of the mob's random as it is now, its {@code LegacyRandomSource}'s, or -1. */
    private static long seedOf(net.minecraft.world.entity.Mob mob) {
        Object random = mob.getRandom();
        try {
            var field = random.getClass().getDeclaredField("seed");
            field.setAccessible(true);
            Object value = field.get(random);
            if (value instanceof java.util.concurrent.atomic.AtomicLong seed) {
                return seed.get();
            }
            return value instanceof Long seed ? seed : -1L;
        } catch (ReflectiveOperationException e) {
            return -1L;
        }
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
