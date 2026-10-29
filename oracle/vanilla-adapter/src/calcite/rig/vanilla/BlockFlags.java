package calcite.rig.vanilla;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.FluidState;

/**
 * Writes what each block state is, as vanilla's state cache holds it, to the JSON file named by
 * its argument: one number a state, in state ID order, read by oracle/datagen/calx_tables.py
 * (oracle/datagen/README.md). Run by oracle/datagen/block_flags.py.
 *
 * <p>Every value is fixed when the states are made, before any data pack loads, so the table is
 * the same for every world.
 */
final class BlockFlags {
    static final int AIR = 1;
    static final int RANDOMLY_TICKING = 1 << 1;
    static final int FLUID = 1 << 2;
    static final int FLUID_RANDOMLY_TICKING = 1 << 3;
    static final int PROPAGATES_SKYLIGHT_DOWN = 1 << 4;
    static final int SHAPE_FOR_LIGHT_OCCLUSION = 1 << 5;
    static final int CAN_OCCLUDE = 1 << 6;
    static final int SOLID_RENDER = 1 << 7;
    static final int BLOCK_ENTITY = 1 << 8;
    static final int LIGHT_EMISSION_SHIFT = 12;
    static final int LIGHT_DAMPENING_SHIFT = 16;

    private BlockFlags() {}

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: BlockFlags OUTPUT.json");
        }
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        int count = Block.BLOCK_STATE_REGISTRY.size();
        StringBuilder json = new StringBuilder();
        json.append("{\n  \"game_version\": \"").append(SharedConstants.getCurrentVersion().name()).append("\",\n");
        json.append("  \"states\": ").append(count).append(",\n  \"flags\": [");
        for (int id = 0; id < count; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            if (state == null || Block.BLOCK_STATE_REGISTRY.getId(state) != id) {
                throw new IllegalStateException("block state " + id + " is missing");
            }
            json.append(id == 0 ? "" : ", ").append(flags(state));
        }
        json.append("]\n}\n");
        Files.writeString(Path.of(args[0]), json, StandardCharsets.UTF_8);
        System.err.println("BlockFlags: wrote " + count + " states to " + args[0]);
    }

    private static int flags(BlockState state) {
        FluidState fluid = state.getFluidState();
        int f = 0;
        f |= state.isAir() ? AIR : 0;
        f |= state.isRandomlyTicking() ? RANDOMLY_TICKING : 0;
        f |= fluid.isEmpty() ? 0 : FLUID;
        f |= fluid.isRandomlyTicking() ? FLUID_RANDOMLY_TICKING : 0;
        f |= state.propagatesSkylightDown() ? PROPAGATES_SKYLIGHT_DOWN : 0;
        f |= state.useShapeForLightOcclusion() ? SHAPE_FOR_LIGHT_OCCLUSION : 0;
        f |= state.canOcclude() ? CAN_OCCLUDE : 0;
        f |= state.isSolidRender() ? SOLID_RENDER : 0;
        f |= state.hasBlockEntity() ? BLOCK_ENTITY : 0;
        f |= state.getLightEmission() << LIGHT_EMISSION_SHIFT;
        f |= state.getLightDampening() << LIGHT_DAMPENING_SHIFT;
        return f;
    }
}
