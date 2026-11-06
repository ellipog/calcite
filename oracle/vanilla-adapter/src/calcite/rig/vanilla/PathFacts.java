package calcite.rig.vanilla;

import java.lang.reflect.Method;
import java.util.Collection;
import java.util.List;
import java.util.stream.StreamSupport;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.tags.TagKey;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.BaseRailBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.FenceGateBlock;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.material.Fluid;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.level.pathfinder.PathComputationType;
import net.minecraft.world.level.pathfinder.PathType;
import net.minecraft.world.level.pathfinder.WalkNodeEvaluator;

/**
 * What pathfinding reads of each block state (CAL-157), for {@link EntityFacts}: what {@code
 * WalkNodeEvaluator.getPathTypeFromState} asks of it besides the world's tags, which Calcite reads
 * from the world's data packs.
 *
 * <p>Each state's facts are a number: bits {@code 2t} and {@code 2t + 1} what {@code
 * isPathfindable} gives for the {@code t}th of {@code LAND}, {@code WATER} and {@code AIR}, never,
 * always, where its fluid is in {@code #water}, or where its fluid isn't in {@code #lava}; and from
 * bit 6 the class it is that the path type asks about, a door open, shut and opened by hand or
 * shut and not, a rail, leaves, a fence gate shut, or none of them. {@code isPathfindable} reads
 * no tags but those two fluid tags, so it's asked of each state twice, with no fluid in either
 * tag and with every fluid in both: what it gives the same both times it always or never gives,
 * and what changes it reads the tag that change shows.
 *
 * <p>Then vanilla's tags are loaded, as a server loads them, and for each state the path type
 * worked out from its facts and those tags, as Calcite works it out, is checked against what
 * {@code getPathTypeFromState} gives, and what its facts say {@code isPathfindable} gives against
 * what it gives; it fails if any differ. What {@code getPathTypeFromState} gives each state with
 * vanilla's tags, and those tags, are written too, for Calcite's test.
 */
final class PathFacts {
    private PathFacts() {}

    static final PathComputationType[] COMPUTATIONS = {PathComputationType.LAND, PathComputationType.WATER, PathComputationType.AIR};
    /** What {@code isPathfindable} gives, as a state's facts hold it. */
    static final int NEVER = 0;
    static final int ALWAYS = 1;
    static final int IN_WATER = 2;
    static final int NOT_IN_LAVA = 3;
    /** Where a state's class is in its facts, and the classes. */
    static final int KIND_SHIFT = 6;
    static final int OTHER = 0;
    static final int DOOR_OPEN = 1;
    static final int DOOR_BY_HAND = 2;
    static final int DOOR_SHUT = 3;
    static final int RAIL = 4;
    static final int LEAVES = 5;
    static final int GATE_SHUT = 6;
    /** The tags {@code getPathTypeFromState} reads. */
    static final List<TagKey<Block>> BLOCK_TAGS =
        List.of(BlockTags.TRAPDOORS, BlockTags.SPELEOTHEMS, BlockTags.FENCES, BlockTags.WALLS, BlockTags.FIRE, BlockTags.CAMPFIRES);
    static final List<TagKey<Fluid>> FLUID_TAGS = List.of(FluidTags.WATER, FluidTags.LAVA);

    /** Each state's facts, in ID order, with the tags as {@code Bootstrap} leaves them, empty. */
    static int[] facts(int states) throws ReflectiveOperationException {
        Method bind = Holder.Reference.class.getDeclaredMethod("bindTags", Collection.class);
        bind.setAccessible(true);
        boolean[] none = pathfindable(states);
        bindFluids(bind, FLUID_TAGS);
        boolean[] every = pathfindable(states);
        bindFluids(bind, List.of());
        int[] out = new int[states];
        for (int id = 0; id < states; id++) {
            int bits = 0;
            for (int t = 0; t < COMPUTATIONS.length; t++) {
                boolean a = none[id * COMPUTATIONS.length + t];
                boolean b = every[id * COMPUTATIONS.length + t];
                int code = a ? (b ? ALWAYS : NOT_IN_LAVA) : (b ? IN_WATER : NEVER);
                bits |= code << (2 * t);
            }
            out[id] = bits | kind(Block.BLOCK_STATE_REGISTRY.byId(id)) << KIND_SHIFT;
        }
        return out;
    }

    private static void bindFluids(Method bind, List<TagKey<Fluid>> tags) throws ReflectiveOperationException {
        for (Fluid fluid : BuiltInRegistries.FLUID) {
            bind.invoke(fluid.builtInRegistryHolder(), tags);
        }
    }

    private static boolean[] pathfindable(int states) {
        boolean[] out = new boolean[states * COMPUTATIONS.length];
        for (int id = 0; id < states; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            for (int t = 0; t < COMPUTATIONS.length; t++) {
                out[id * COMPUTATIONS.length + t] = state.isPathfindable(COMPUTATIONS[t]);
            }
        }
        return out;
    }

    private static int kind(BlockState state) {
        Block block = state.getBlock();
        if (block instanceof DoorBlock door) {
            if (state.getValue(DoorBlock.OPEN)) {
                return DOOR_OPEN;
            }
            return door.type().canOpenByHand() ? DOOR_BY_HAND : DOOR_SHUT;
        }
        if (block instanceof BaseRailBlock) {
            return RAIL;
        }
        if (block instanceof LeavesBlock) {
            return LEAVES;
        }
        if (block instanceof FenceGateBlock && !state.getValue(FenceGateBlock.OPEN)) {
            return GATE_SHUT;
        }
        return OTHER;
    }

    /**
     * With vanilla's tags loaded, what {@code getPathTypeFromState} gives each state, by {@code
     * PathType}'s ordinal, in ID order, each checked against what {@code facts} make of it.
     */
    static int[] check(int[] facts) throws ReflectiveOperationException {
        RegistriesProbe.load();
        Method from = WalkNodeEvaluator.class.getDeclaredMethod("getPathTypeFromState", BlockGetter.class, BlockPos.class);
        from.setAccessible(true);
        int[] out = new int[facts.length];
        for (int id = 0; id < facts.length; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            for (int t = 0; t < COMPUTATIONS.length; t++) {
                if (pathfindable(state, facts[id], t) != state.isPathfindable(COMPUTATIONS[t])) {
                    throw new IllegalStateException("state " + id + " (" + state + ")'s facts say otherwise of isPathfindable(" + COMPUTATIONS[t] + ")");
                }
            }
            PathType vanilla = (PathType) from.invoke(null, new OneState(state), BlockPos.ZERO);
            PathType ours = pathType(state, facts[id]);
            if (vanilla != ours) {
                throw new IllegalStateException("state " + id + " (" + state + ") is " + vanilla + " to vanilla, " + ours + " from its facts");
            }
            out[id] = vanilla.ordinal();
        }
        return out;
    }

    // What the state's facts say `isPathfindable` gives for the `t`th computation, with the tags.
    private static boolean pathfindable(BlockState state, int facts, int t) {
        FluidState fluid = state.getFluidState();
        return switch ((facts >> (2 * t)) & 3) {
            case ALWAYS -> true;
            case IN_WATER -> fluid.is(FluidTags.WATER);
            case NOT_IN_LAVA -> !fluid.is(FluidTags.LAVA);
            default -> false;
        };
    }

    // The path type, as Calcite works it out from the state's facts and the tags.
    private static PathType pathType(BlockState state, int facts) {
        if (state.isAir()) {
            return PathType.OPEN;
        }
        if (state.is(BlockTags.TRAPDOORS) || state.is(Blocks.LILY_PAD) || state.is(Blocks.BIG_DRIPLEAF)) {
            return PathType.TRAPDOOR;
        }
        if (state.is(Blocks.POWDER_SNOW)) {
            return PathType.POWDER_SNOW;
        }
        if (state.is(Blocks.CACTUS) || state.is(Blocks.SWEET_BERRY_BUSH)) {
            return PathType.DAMAGING;
        }
        if (state.is(Blocks.HONEY_BLOCK)) {
            return PathType.STICKY_HONEY;
        }
        if (state.is(Blocks.COCOA)) {
            return PathType.COCOA;
        }
        if (state.is(Blocks.WITHER_ROSE) || state.is(BlockTags.SPELEOTHEMS)) {
            return PathType.DAMAGE_CAUTIOUS;
        }
        if (state.getFluidState().is(FluidTags.LAVA)) {
            return PathType.LAVA;
        }
        boolean lit = state.hasProperty(BlockStateProperties.LIT) && state.is(BlockTags.CAMPFIRES) && state.getValue(BlockStateProperties.LIT);
        if (state.is(BlockTags.FIRE) || state.is(Blocks.LAVA) || state.is(Blocks.MAGMA_BLOCK) || lit || state.is(Blocks.LAVA_CAULDRON)) {
            return PathType.FIRE;
        }
        int kind = facts >> KIND_SHIFT;
        switch (kind) {
            case DOOR_OPEN:
                return PathType.DOOR_OPEN;
            case DOOR_BY_HAND:
                return PathType.DOOR_WOOD_CLOSED;
            case DOOR_SHUT:
                return PathType.DOOR_IRON_CLOSED;
            case RAIL:
                return PathType.RAIL;
            case LEAVES:
                return PathType.LEAVES;
            default:
                break;
        }
        if (state.is(BlockTags.FENCES) || state.is(BlockTags.WALLS) || kind == GATE_SHUT) {
            return PathType.FENCE;
        }
        if (!pathfindable(state, facts, 0)) {
            return PathType.BLOCKED;
        }
        return state.getFluidState().is(FluidTags.WATER) ? PathType.WATER : PathType.OPEN;
    }

    /** The blocks of each of {@link #BLOCK_TAGS}, by ID, with vanilla's tags loaded. */
    static int[][] blockTags() {
        int[][] out = new int[BLOCK_TAGS.size()][];
        for (int i = 0; i < out.length; i++) {
            out[i] = StreamSupport.stream(BuiltInRegistries.BLOCK.getTagOrEmpty(BLOCK_TAGS.get(i)).spliterator(), false).mapToInt(h -> BuiltInRegistries.BLOCK.getId(h.value())).sorted().toArray();
        }
        return out;
    }

    /** The fluids of each of {@link #FLUID_TAGS}, by ID, with vanilla's tags loaded. */
    static int[][] fluidTags() {
        int[][] out = new int[FLUID_TAGS.size()][];
        for (int i = 0; i < out.length; i++) {
            out[i] = StreamSupport.stream(BuiltInRegistries.FLUID.getTagOrEmpty(FLUID_TAGS.get(i)).spliterator(), false).mapToInt(h -> BuiltInRegistries.FLUID.getId(h.value())).sorted().toArray();
        }
        return out;
    }

    // A level of one state, at the origin, and air.
    private record OneState(BlockState state) implements BlockGetter {
        @Override
        public BlockEntity getBlockEntity(BlockPos pos) {
            return null;
        }

        @Override
        public BlockState getBlockState(BlockPos pos) {
            return pos.equals(BlockPos.ZERO) ? this.state : Blocks.AIR.defaultBlockState();
        }

        @Override
        public FluidState getFluidState(BlockPos pos) {
            return this.getBlockState(pos).getFluidState();
        }

        @Override
        public int getHeight() {
            return 384;
        }

        @Override
        public int getMinY() {
            return -64;
        }
    }
}
