package calcite.rig.vanilla;

import com.google.common.math.DoubleMath;
import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.entity.ai.village.poi.PoiTypes;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.EmptyBlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.SupportType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.lighting.LightEngine;
import net.minecraft.world.level.material.FlowingFluid;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/**
 * Writes what each block state is, as vanilla's state cache holds it, to the JSON file named by
 * its argument: one number a state, in state ID order, read by oracle/datagen/calx_tables.py
 * (oracle/datagen/README.md). Run by oracle/datagen/block_flags.py.
 *
 * <p>It also writes the faces light sees: for each state, the shape {@code
 * LightEngine.getOcclusionShape} gives on each of its six sides, as a number for each different
 * shape, and for each two shapes whether {@code Shapes.faceShapeOccludes} says light can't pass
 * between them. Shape 0 is empty and shape 1 the full face.
 *
 * <p>And each state's collision shape, as {@code PlayerSpawnFinder} sees it: {@code
 * getCollisionShape} with an empty context that collides with fluids, so a liquid is a whole
 * block, numbered as the faces are, with the boxes of each shape. A state whose shape vanilla
 * offsets by its position, as bamboo's, gets the shape it has before it's offset, and the flag
 * {@code OFFSET}. {@code COLLISION_TOP_FULL} is whether the shape with an empty context covers
 * its block's top, {@code Block.isFaceFull} on {@code UP}, and {@code LARGE_COLLISION} is {@code
 * hasLargeCollisionShape}, whether it reaches out of its block or changes with where it is.
 *
 * <p>And the faces a fluid sees of each state (CAL-91): its collision shape with an empty context,
 * as {@code FlowingFluid.canPassThroughWall} asks it, toward each side, as {@code
 * Shapes.mergedFaceOccludes} takes it: empty unless the shape reaches that side of its block, else
 * the boxes that reach it, laid flat on the face's other two axes, x before y before z, one block
 * deep along z. They're numbered as the light's faces are, with whether each two cover a face
 * between them. A state vanilla offsets by its position whose collision shape isn't empty, as
 * pointed dripstone, moves: its faces are where it is, so it's written with its boxes before
 * they're offset and where its shape's grid starts and ends on each axis, as {@code
 * mergedFaceOccludes} slices the grid's end cell, which moving can leave empty, and each block with
 * an offset with how far it goes. Every two shapes the states
 * have, each way round and toward each side, are checked against vanilla's own {@code
 * canPassThroughWall}, and each state that moves at 24 places against every shape, so the table
 * says what vanilla does or this fails; the cases where a state's moving changes the answer are
 * written for Calcite's own test.
 *
 * <p>And each state's collision shape as an entity moves against it (CAL-148): {@code
 * getCollisionShape} with an empty context, so a liquid has none, before vanilla offsets it by its
 * position, numbered as the others are, with the boxes of each; each block whose friction, speed
 * factor, jump factor or bounce isn't the default, as {@code Entity.move} reads them; and cases of
 * vanilla's own {@code VoxelShape.collide}, for each of those shapes, of boxes near it that don't
 * overlap it, as an entity's box doesn't while it has physics, moved along an axis, for Calcite's
 * test.
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
    static final int COLLISION_TOP_FULL = 1 << 9;
    static final int LARGE_COLLISION = 1 << 10;
    static final int OFFSET = 1 << 11;
    static final int LIGHT_EMISSION_SHIFT = 12;
    static final int LIGHT_DAMPENING_SHIFT = 16;

    // What features ask of a state: its `facts`.
    static final int SOLID = 1;
    static final int REPLACEABLE = 1 << 1;
    static final int COLLISION_EMPTY = 1 << 2;
    static final int COLLISION_FULL_BLOCK = 1 << 3;
    static final int LIQUID = 1 << 4;
    static final int IGNITED_BY_LAVA = 1 << 5;
    static final int REDSTONE_CONDUCTOR = 1 << 6;
    static final int STURDY_FULL_SHIFT = 7;
    static final int STURDY_CENTER_SHIFT = 13;
    static final int STURDY_RIGID_SHIFT = 19;
    static final int COLLISION_FACE_SHIFT = 25;
    static final int COLLISION_TOP_ANY = 1 << 31;
    // The fluid, in a long's high half.
    static final int FLUID_TYPE_SHIFT = 32;
    static final int FLUID_AMOUNT_SHIFT = 36;
    // Which faces the occlusion shape covers whole, a bit each from here.
    static final int OCCLUSION_FACE_SHIFT = 40;

    private BlockFlags() {}

    public static void main(String[] args) throws IOException, ReflectiveOperationException {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: BlockFlags OUTPUT.json");
        }
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        int count = Block.BLOCK_STATE_REGISTRY.size();
        Faces faces = new Faces();
        Faces collisions = new Faces();
        Faces movements = new Faces();
        Faces fluidFaces = new Faces();
        int[][] fluidFaceIds = new int[count][Direction.values().length];
        StringBuilder fluid = new StringBuilder();
        StringBuilder json = new StringBuilder();
        StringBuilder light = new StringBuilder();
        StringBuilder collision = new StringBuilder();
        StringBuilder movement = new StringBuilder();
        StringBuilder facts = new StringBuilder();
        // The states whose shape is a full block where their collision shape isn't, or the other
        // way round: what `Block.isShapeFullBlock(getShape)` says, as an exception to
        // `isCollisionShapeFullBlock`.
        StringBuilder outline = new StringBuilder();
        // The states whose collision shape's bottom covers `WallBlock`'s test shapes otherwise
        // than its face being full says, all of them or none: each state and its mask, a bit for
        // the post's test and then one for the north, east, south and west wall's.
        StringBuilder wallCover = new StringBuilder();
        VoxelShape postTest = Block.column(2.0, 0.0, 16.0);
        Map<Direction, VoxelShape> wallTests = Shapes.rotateHorizontal(Block.boxZ(2.0, 16.0, 0.0, 9.0));
        VoxelShape[] coverTests = {postTest, wallTests.get(Direction.NORTH), wallTests.get(Direction.EAST),
                wallTests.get(Direction.SOUTH), wallTests.get(Direction.WEST)};
        json.append("{\n  \"game_version\": \"").append(SharedConstants.getCurrentVersion().name()).append("\",\n");
        json.append("  \"states\": ").append(count).append(",\n  \"flags\": [");
        for (int id = 0; id < count; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            if (state == null || Block.BLOCK_STATE_REGISTRY.getId(state) != id) {
                throw new IllegalStateException("block state " + id + " is missing");
            }
            json.append(id == 0 ? "" : ", ").append(flags(state));
            light.append(id == 0 ? "[" : ", [");
            for (Direction direction : Direction.values()) {
                light.append(direction.ordinal() == 0 ? "" : ", ").append(faces.id(LightEngine.getOcclusionShape(state, direction)));
            }
            light.append("]");
            collision.append(id == 0 ? "" : ", ").append(collisions.id(collisionShape(state)));
            movement.append(id == 0 ? "" : ", ").append(movements.id(fluidShape(state)));
            VoxelShape walls = fluidShape(state);
            fluid.append(id == 0 ? "[" : ", [");
            for (Direction direction : Direction.values()) {
                int face = fluidFaces.id(fluidFace(walls, direction));
                fluidFaceIds[id][direction.ordinal()] = face;
                fluid.append(direction.ordinal() == 0 ? "" : ", ").append(face);
            }
            fluid.append("]");
            facts.append(id == 0 ? "" : ", ").append(facts(state));
            boolean shapeFull = Block.isShapeFullBlock(state.getShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO));
            if (shapeFull != state.isCollisionShapeFullBlock(EmptyBlockGetter.INSTANCE, BlockPos.ZERO)) {
                outline.append(outline.isEmpty() ? "" : ", ").append(id);
            }
            VoxelShape below = state.getCollisionShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO);
            VoxelShape bottom = below.getFaceShape(Direction.DOWN);
            int cover = 0;
            for (int i = 0; i < coverTests.length; i++) {
                if (!Shapes.joinIsNotEmpty(coverTests[i], bottom, net.minecraft.world.phys.shapes.BooleanOp.ONLY_FIRST)) {
                    cover |= 1 << i;
                }
            }
            if (cover != (Block.isFaceFull(below, Direction.DOWN) ? 31 : 0)) {
                wallCover.append(wallCover.isEmpty() ? "[" : ", [").append(id).append(", ").append(cover).append("]");
            }
        }
        StringBuilder poi = new StringBuilder();
        for (int id = 0; id < count; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            int type = PoiTypes.forState(state).map(h -> BuiltInRegistries.POINT_OF_INTEREST_TYPE.getId(h.value())).orElse(-1);
            if (type >= 0) {
                poi.append(poi.isEmpty() ? "[" : ", [").append(id).append(", ").append(type).append("]");
            }
        }
        // `BlockState.rotate` and `mirror`, as structure templates turn what they place: for each
        // state any of them changes, the state, then what clockwise 90, 180 and counterclockwise 90
        // make of it, then the mirrors left to right and front to back.
        StringBuilder turns = new StringBuilder();
        for (int id = 0; id < count; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            BlockState[] made = {
                state.rotate(Rotation.CLOCKWISE_90), state.rotate(Rotation.CLOCKWISE_180),
                state.rotate(Rotation.COUNTERCLOCKWISE_90), state.mirror(Mirror.LEFT_RIGHT), state.mirror(Mirror.FRONT_BACK),
            };
            boolean changes = false;
            for (BlockState m : made) {
                changes |= m != state;
            }
            if (changes) {
                turns.append(turns.isEmpty() ? "[" : ", [").append(id);
                for (BlockState m : made) {
                    turns.append(", ").append(Block.BLOCK_STATE_REGISTRY.getId(m));
                }
                turns.append("]");
            }
        }
        StringBuilder classes = new StringBuilder();
        StringBuilder survive = new StringBuilder();
        StringBuilder placeOn = new StringBuilder();
        StringBuilder shape = new StringBuilder();
        // What a block does as the blocks around it change, as it's placed, once it's gone, as
        // its scheduled tick runs, as a random tick comes to it and as rain or snow falls on it:
        // the class whose `neighborChanged`, `onPlace`, `affectNeighborsAfterRemoval`, `tick`
        // (D325), `randomTick` (D338) and `handlePrecipitation` (D340) it runs.
        StringBuilder neighbour = new StringBuilder();
        StringBuilder place = new StringBuilder();
        StringBuilder removal = new StringBuilder();
        StringBuilder tick = new StringBuilder();
        StringBuilder randomTick = new StringBuilder();
        StringBuilder precipitation = new StringBuilder();
        // The signal a block gives, weak and strong, its own, which `BlockBehaviour.getSignal`
        // gives, and whether it's a source of one: the class whose `getSignal`, `getDirectSignal`,
        // `ownSignal` and `isSignalSource` it runs (CAL-116).
        StringBuilder signal = new StringBuilder();
        StringBuilder ownSignal = new StringBuilder();
        StringBuilder directSignal = new StringBuilder();
        StringBuilder signalSource = new StringBuilder();
        // What a comparator reads of a block behind it: the class whose `hasAnalogOutputSignal`
        // and `getAnalogOutputSignal` it runs (CAL-123).
        StringBuilder hasAnalog = new StringBuilder();
        StringBuilder analog = new StringBuilder();
        // What placing a block and using one ask of it (CAL-139): the class whose
        // `getStateForPlacement`, `canBeReplaced` for a placement, `setPlacedBy`, `useItemOn` and
        // `useWithoutItem` it runs.
        StringBuilder placement = new StringBuilder();
        StringBuilder replace = new StringBuilder();
        StringBuilder placedBy = new StringBuilder();
        StringBuilder useItem = new StringBuilder();
        StringBuilder useWithout = new StringBuilder();
        // `FireBlock.canBurn`: the blocks fire's ignite odds are above 0 for; and each block with
        // either of fire's odds above 0, with its ignite odds and its burn odds (D339).
        StringBuilder flammable = new StringBuilder();
        StringBuilder fireOdds = new StringBuilder();
        // The blocks that are `LiquidBlockContainer`s, as structure templates fill them: those that
        // are `SimpleWaterloggedBlock`s, and the others.
        StringBuilder waterloggable = new StringBuilder();
        StringBuilder containers = new StringBuilder();
        // `Block.hasDynamicShape`: blocks whose shape can change where they stand.
        StringBuilder dynamic = new StringBuilder();
        // `BlockState.instrument()`, which a note block plays over each block: a block's states all
        // have its properties' one, as an ordinal of `NoteBlockInstrument`, with the instruments'
        // names and those that `worksAboveNoteBlock`.
        StringBuilder instruments = new StringBuilder();
        StringBuilder instrumentNames = new StringBuilder();
        StringBuilder instrumentsAbove = new StringBuilder();
        for (net.minecraft.world.level.block.state.properties.NoteBlockInstrument i
                : net.minecraft.world.level.block.state.properties.NoteBlockInstrument.values()) {
            instrumentNames.append(instrumentNames.isEmpty() ? "\"" : ", \"").append(i.getSerializedName()).append("\"");
            if (i.worksAboveNoteBlock()) {
                instrumentsAbove.append(instrumentsAbove.isEmpty() ? "" : ", ").append(i.ordinal());
            }
        }
        java.lang.reflect.Field igniteField = net.minecraft.world.level.block.FireBlock.class.getDeclaredField("igniteOdds");
        igniteField.setAccessible(true);
        @SuppressWarnings("unchecked")
        it.unimi.dsi.fastutil.objects.Object2IntMap<Block> ignite =
                (it.unimi.dsi.fastutil.objects.Object2IntMap<Block>) igniteField.get(net.minecraft.world.level.block.Blocks.FIRE);
        java.lang.reflect.Field burnField = net.minecraft.world.level.block.FireBlock.class.getDeclaredField("burnOdds");
        burnField.setAccessible(true);
        @SuppressWarnings("unchecked")
        it.unimi.dsi.fastutil.objects.Object2IntMap<Block> burn =
                (it.unimi.dsi.fastutil.objects.Object2IntMap<Block>) burnField.get(net.minecraft.world.level.block.Blocks.FIRE);
        Map<String, String> parents = new java.util.TreeMap<>();
        // Each block's `getPistonPushReaction`, by its ordinal, and the blocks whose destroy speed is
        // -1, which a piston can't move (CAL-125). Each is a field each state copies from its block's
        // properties, so every state of a block has the same; that's checked.
        StringBuilder pushReactions = new StringBuilder();
        StringBuilder unbreakable = new StringBuilder();
        // Each block's destroy speed, `getDestroySpeed`, and the blocks that need the right tool
        // for their drops, `requiresCorrectToolForDrops`, which digging reads (CAL-138). Each state
        // copies them from its block's properties too; that's checked.
        StringBuilder destroySpeeds = new StringBuilder();
        StringBuilder needsTool = new StringBuilder();
        // The sounds a block that a signal opens or presses plays, on and off (CAL-124): a door's,
        // a trapdoor's and a button's and a pressure plate's from its `BlockSetType`, a fence gate's
        // from its `WoodType`, each by the sound event's name.
        StringBuilder toggles = new StringBuilder();
        // How long a button stays pressed, `ticksToStayPressed`, and how many entities a weighted
        // pressure plate weighs at most, `maxWeight` (CAL-128).
        StringBuilder buttonTicks = new StringBuilder();
        StringBuilder plateWeights = new StringBuilder();
        for (int id = 0; id < BuiltInRegistries.BLOCK.size(); id++) {
            Block block = BuiltInRegistries.BLOCK.byId(id);
            String[] sounds = toggleSounds(block);
            if (sounds != null) {
                toggles.append(toggles.isEmpty() ? "" : ", ").append("[").append(id).append(", \"").append(sounds[0]).append("\", \"").append(sounds[1]).append("\"]");
            }
            if (block instanceof net.minecraft.world.level.block.ButtonBlock) {
                buttonTicks.append(buttonTicks.isEmpty() ? "" : ", ").append("[").append(id).append(", ").append(fieldOf(block, "ticksToStayPressed")).append("]");
            }
            if (block instanceof net.minecraft.world.level.block.WeightedPressurePlateBlock) {
                plateWeights.append(plateWeights.isEmpty() ? "" : ", ").append("[").append(id).append(", ").append(fieldOf(block, "maxWeight")).append("]");
            }
            BlockState first = block.getStateDefinition().getPossibleStates().get(0);
            int reaction = first.getPistonPushReaction().ordinal();
            boolean fixed = first.getDestroySpeed(EmptyBlockGetter.INSTANCE, BlockPos.ZERO) == -1.0F;
            for (BlockState s : block.getStateDefinition().getPossibleStates()) {
                if (s.getPistonPushReaction().ordinal() != reaction || (s.getDestroySpeed(EmptyBlockGetter.INSTANCE, BlockPos.ZERO) == -1.0F) != fixed) {
                    throw new IllegalStateException("BlockFlags: the states of " + BuiltInRegistries.BLOCK.getKey(block) + " differ in how a piston moves them");
                }
            }
            pushReactions.append(id == 0 ? "" : ", ").append(reaction);
            if (fixed) {
                unbreakable.append(unbreakable.isEmpty() ? "" : ", ").append(id);
            }
            float speed = first.getDestroySpeed(EmptyBlockGetter.INSTANCE, BlockPos.ZERO);
            boolean tool = first.requiresCorrectToolForDrops();
            for (BlockState s : block.getStateDefinition().getPossibleStates()) {
                if (Float.compare(s.getDestroySpeed(EmptyBlockGetter.INSTANCE, BlockPos.ZERO), speed) != 0 || s.requiresCorrectToolForDrops() != tool) {
                    throw new IllegalStateException("BlockFlags: the states of " + BuiltInRegistries.BLOCK.getKey(block) + " differ in how they're dug");
                }
            }
            destroySpeeds.append(id == 0 ? "" : ", ").append(speed);
            if (tool) {
                needsTool.append(needsTool.isEmpty() ? "" : ", ").append(id);
            }
        }
        for (int id = 0; id < BuiltInRegistries.BLOCK.size(); id++) {
            Class<?> type = BuiltInRegistries.BLOCK.byId(id).getClass();
            while (type.isAnonymousClass()) {
                type = type.getSuperclass();
            }
            classes.append(id == 0 ? "\"" : ", \"").append(type.getSimpleName()).append("\"");
            for (Class<?> c = type; c != null && c != Object.class; c = c.getSuperclass()) {
                Class<?> parent = c.getSuperclass();
                parents.put(c.getSimpleName(), parent == null || parent == Object.class ? "" : parent.getSimpleName());
            }
            String s = declaring(type, "canSurvive", BlockState.class, net.minecraft.world.level.LevelReader.class, BlockPos.class);
            String p = declaring(type, "mayPlaceOn", BlockState.class, net.minecraft.world.level.BlockGetter.class, BlockPos.class);
            survive.append(id == 0 ? "\"" : ", \"").append(s).append("\"");
            placeOn.append(id == 0 ? "\"" : ", \"").append(p).append("\"");
            String u = declaring(type, "updateShape", BlockState.class, net.minecraft.world.level.LevelReader.class,
                    net.minecraft.world.level.ScheduledTickAccess.class, BlockPos.class, Direction.class, BlockPos.class,
                    BlockState.class, net.minecraft.util.RandomSource.class);
            int igniteOdds = ignite.getInt(BuiltInRegistries.BLOCK.byId(id));
            int burnOdds = burn.getInt(BuiltInRegistries.BLOCK.byId(id));
            if (igniteOdds > 0) {
                flammable.append(flammable.isEmpty() ? "" : ", ").append(id);
            }
            if (igniteOdds > 0 || burnOdds > 0) {
                fireOdds.append(fireOdds.isEmpty() ? "[" : ", [").append(id).append(", ").append(igniteOdds).append(", ").append(burnOdds).append("]");
            }
            shape.append(id == 0 ? "\"" : ", \"").append(u).append("\"");
            String nc = declaring(type, "neighborChanged", BlockState.class, net.minecraft.world.level.Level.class, BlockPos.class,
                    Block.class, net.minecraft.world.level.redstone.Orientation.class, boolean.class);
            String op = declaring(type, "onPlace", BlockState.class, net.minecraft.world.level.Level.class, BlockPos.class,
                    BlockState.class, boolean.class);
            String ar = declaring(type, "affectNeighborsAfterRemoval", BlockState.class, net.minecraft.server.level.ServerLevel.class,
                    BlockPos.class, boolean.class);
            String tk = declaring(type, "tick", BlockState.class, net.minecraft.server.level.ServerLevel.class, BlockPos.class,
                    net.minecraft.util.RandomSource.class);
            String rt = declaring(type, "randomTick", BlockState.class, net.minecraft.server.level.ServerLevel.class, BlockPos.class,
                    net.minecraft.util.RandomSource.class);
            String hp = declaring(type, "handlePrecipitation", BlockState.class, net.minecraft.world.level.Level.class, BlockPos.class,
                    net.minecraft.world.level.biome.Biome.Precipitation.class);
            neighbour.append(id == 0 ? "\"" : ", \"").append(nc).append("\"");
            place.append(id == 0 ? "\"" : ", \"").append(op).append("\"");
            removal.append(id == 0 ? "\"" : ", \"").append(ar).append("\"");
            tick.append(id == 0 ? "\"" : ", \"").append(tk).append("\"");
            randomTick.append(id == 0 ? "\"" : ", \"").append(rt).append("\"");
            precipitation.append(id == 0 ? "\"" : ", \"").append(hp).append("\"");
            String gs = declaring(type, "getSignal", BlockState.class, net.minecraft.world.level.BlockGetter.class, BlockPos.class,
                    Direction.class);
            String ds = declaring(type, "getDirectSignal", BlockState.class, net.minecraft.world.level.BlockGetter.class,
                    BlockPos.class, Direction.class);
            String ss = declaring(type, "isSignalSource", BlockState.class);
            String os = declaring(type, "ownSignal", BlockState.class, net.minecraft.world.level.BlockGetter.class, BlockPos.class);
            ownSignal.append(id == 0 ? "\"" : ", \"").append(os).append("\"");
            signal.append(id == 0 ? "\"" : ", \"").append(gs).append("\"");
            directSignal.append(id == 0 ? "\"" : ", \"").append(ds).append("\"");
            signalSource.append(id == 0 ? "\"" : ", \"").append(ss).append("\"");
            String ha = declaring(type, "hasAnalogOutputSignal", BlockState.class);
            String ga = declaring(type, "getAnalogOutputSignal", BlockState.class, net.minecraft.world.level.Level.class,
                    BlockPos.class, Direction.class);
            hasAnalog.append(id == 0 ? "\"" : ", \"").append(ha).append("\"");
            analog.append(id == 0 ? "\"" : ", \"").append(ga).append("\"");
            String gp = declaring(type, "getStateForPlacement", net.minecraft.world.item.context.BlockPlaceContext.class);
            String cr = declaring(type, "canBeReplaced", BlockState.class, net.minecraft.world.item.context.BlockPlaceContext.class);
            String pb = declaring(type, "setPlacedBy", net.minecraft.world.level.Level.class, BlockPos.class, BlockState.class,
                    net.minecraft.world.entity.LivingEntity.class, net.minecraft.world.item.ItemStack.class);
            String ui = declaring(type, "useItemOn", net.minecraft.world.item.ItemStack.class, BlockState.class,
                    net.minecraft.world.level.Level.class, BlockPos.class, net.minecraft.world.entity.player.Player.class,
                    net.minecraft.world.InteractionHand.class, net.minecraft.world.phys.BlockHitResult.class);
            String uw = declaring(type, "useWithoutItem", BlockState.class, net.minecraft.world.level.Level.class, BlockPos.class,
                    net.minecraft.world.entity.player.Player.class, net.minecraft.world.phys.BlockHitResult.class);
            placement.append(id == 0 ? "\"" : ", \"").append(gp).append("\"");
            replace.append(id == 0 ? "\"" : ", \"").append(cr).append("\"");
            placedBy.append(id == 0 ? "\"" : ", \"").append(pb).append("\"");
            useItem.append(id == 0 ? "\"" : ", \"").append(ui).append("\"");
            useWithout.append(id == 0 ? "\"" : ", \"").append(uw).append("\"");
            Block block = BuiltInRegistries.BLOCK.byId(id);
            int instrument = block.defaultBlockState().instrument().ordinal();
            for (BlockState each : block.getStateDefinition().getPossibleStates()) {
                if (each.instrument().ordinal() != instrument) {
                    throw new IllegalStateException(BuiltInRegistries.BLOCK.getKey(block) + "'s states play more than one instrument");
                }
            }
            instruments.append(id == 0 ? "" : ", ").append(instrument);
            if (block.hasDynamicShape()) {
                dynamic.append(dynamic.isEmpty() ? "" : ", ").append(id);
            }
            if (block instanceof net.minecraft.world.level.block.SimpleWaterloggedBlock) {
                waterloggable.append(waterloggable.isEmpty() ? "" : ", ").append(id);
            } else if (block instanceof net.minecraft.world.level.block.LiquidBlockContainer) {
                containers.append(containers.isEmpty() ? "" : ", ").append(id);
            }
        }
        // Each item whose default `max_stack_size` isn't 64, with it, which a container's comparator
        // output divides each stack by (CAL-123), once their default components are bound as a
        // server binds them.
        RegistriesProbe.load();
        StringBuilder stacks = new StringBuilder();
        for (net.minecraft.world.item.Item item : BuiltInRegistries.ITEM) {
            int most = item.getDefaultMaxStackSize();
            if (most != 64) {
                stacks.append(stacks.isEmpty() ? "[\"" : ", [\"").append(BuiltInRegistries.ITEM.getKey(item)).append("\", ")
                        .append(most).append("]");
            }
        }
        // Each block item (CAL-139): its ID, its block's, its class's name, and, for a
        // `StandingAndWallBlockItem`, its wall block's ID and `attachmentDirection`'s 3D data value,
        // else -1 and -1; then each block's item, `asItem`, by ID, air's 0 for none.
        StringBuilder blockItems = new StringBuilder();
        java.lang.reflect.Field wallField = net.minecraft.world.item.StandingAndWallBlockItem.class.getDeclaredField("wallBlock");
        wallField.setAccessible(true);
        java.lang.reflect.Field attachField = net.minecraft.world.item.StandingAndWallBlockItem.class.getDeclaredField("attachmentDirection");
        attachField.setAccessible(true);
        for (net.minecraft.world.item.Item item : BuiltInRegistries.ITEM) {
            if (!(item instanceof net.minecraft.world.item.BlockItem blockItem)) {
                continue;
            }
            Class<?> kind = item.getClass();
            while (kind.isAnonymousClass()) {
                kind = kind.getSuperclass();
            }
            int wall = -1;
            int attach = -1;
            if (item instanceof net.minecraft.world.item.StandingAndWallBlockItem) {
                wall = BuiltInRegistries.BLOCK.getId((Block) wallField.get(item));
                attach = ((Direction) attachField.get(item)).get3DDataValue();
            }
            blockItems.append(blockItems.isEmpty() ? "[" : ", [").append(BuiltInRegistries.ITEM.getId(item)).append(", ")
                    .append(BuiltInRegistries.BLOCK.getId(blockItem.getBlock())).append(", \"").append(kind.getSimpleName())
                    .append("\", ").append(wall).append(", ").append(attach).append("]");
        }
        StringBuilder itemsOfBlocks = new StringBuilder();
        for (int id = 0; id < BuiltInRegistries.BLOCK.size(); id++) {
            itemsOfBlocks.append(id == 0 ? "" : ", ").append(BuiltInRegistries.ITEM.getId(BuiltInRegistries.BLOCK.byId(id).asItem()));
        }
        // Each state's sound type's place sound, by the sound event's name, with its volume and
        // pitch, which `BlockItem.place` plays (CAL-139): the different ones, then each state's
        // index into them, in state ID order.
        StringBuilder soundTypes = new StringBuilder();
        StringBuilder stateSounds = new StringBuilder();
        Map<String, Integer> soundIndex = new HashMap<>();
        for (int id = 0; id < count; id++) {
            net.minecraft.world.level.block.SoundType type = Block.BLOCK_STATE_REGISTRY.byId(id).getSoundType();
            String key = "\"" + type.getPlaceSound().location().getPath() + "\", " + type.getVolume() + ", " + type.getPitch();
            Integer at = soundIndex.get(key);
            if (at == null) {
                at = soundIndex.size();
                soundIndex.put(key, at);
                soundTypes.append(soundTypes.isEmpty() ? "[" : ", [").append(key).append("]");
            }
            stateSounds.append(id == 0 ? "" : ", ").append(at);
        }
        // Each block with a block entity and its type, as `BlockEntityType.isValid` names it.
        StringBuilder blockEntities = new StringBuilder();
        for (int id = 0; id < BuiltInRegistries.BLOCK.size(); id++) {
            BlockState state = BuiltInRegistries.BLOCK.byId(id).defaultBlockState();
            for (net.minecraft.world.level.block.entity.BlockEntityType<?> type : BuiltInRegistries.BLOCK_ENTITY_TYPE) {
                if (type.isValid(state)) {
                    blockEntities.append(blockEntities.isEmpty() ? "[" : ", [").append(id).append(", \"")
                            .append(BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(type)).append("\"]");
                    break;
                }
            }
        }
        StringBuilder parentJson = new StringBuilder();
        for (Map.Entry<String, String> e : parents.entrySet()) {
            parentJson.append(parentJson.isEmpty() ? "\"" : ", \"").append(e.getKey()).append("\": \"").append(e.getValue()).append("\"");
        }
        json.append("],\n  \"light_faces\": [").append(light).append("],\n");
        json.append("  \"face_boxes\": ");
        boxes(json, faces);
        json.append(",\n  \"facts\": [").append(facts).append("],\n");
        json.append("  \"classes\": [").append(classes).append("],\n");
        json.append("  \"survive_classes\": [").append(survive).append("],\n");
        json.append("  \"place_on_classes\": [").append(placeOn).append("],\n");
        json.append("  \"shape_classes\": [").append(shape).append("],\n");
        json.append("  \"neighbour_classes\": [").append(neighbour).append("],\n");
        json.append("  \"place_classes\": [").append(place).append("],\n");
        json.append("  \"removal_classes\": [").append(removal).append("],\n");
        json.append("  \"tick_classes\": [").append(tick).append("],\n");
        json.append("  \"random_tick_classes\": [").append(randomTick).append("],\n");
        json.append("  \"precipitation_classes\": [").append(precipitation).append("],\n");
        json.append("  \"signal_classes\": [").append(signal).append("],\n");
        json.append("  \"direct_signal_classes\": [").append(directSignal).append("],\n");
        json.append("  \"own_signal_classes\": [").append(ownSignal).append("],\n");
        json.append("  \"signal_source_classes\": [").append(signalSource).append("],\n");
        json.append("  \"has_analog_classes\": [").append(hasAnalog).append("],\n");
        json.append("  \"analog_classes\": [").append(analog).append("],\n");
        json.append("  \"placement_classes\": [").append(placement).append("],\n");
        json.append("  \"replace_classes\": [").append(replace).append("],\n");
        json.append("  \"placed_by_classes\": [").append(placedBy).append("],\n");
        json.append("  \"use_item_classes\": [").append(useItem).append("],\n");
        json.append("  \"use_classes\": [").append(useWithout).append("],\n");
        json.append("  \"block_items\": [").append(blockItems).append("],\n");
        json.append("  \"items_of_blocks\": [").append(itemsOfBlocks).append("],\n");
        json.append("  \"place_sounds\": [").append(soundTypes).append("],\n");
        json.append("  \"state_place_sounds\": [").append(stateSounds).append("],\n");
        json.append("  \"item_stack_sizes\": [").append(stacks).append("],\n");
        json.append("  \"push_reactions\": [").append(pushReactions).append("],\n");
        json.append("  \"unbreakable_blocks\": [").append(unbreakable).append("],\n");
        json.append("  \"destroy_speeds\": [").append(destroySpeeds).append("],\n");
        json.append("  \"needs_tool_blocks\": [").append(needsTool).append("],\n");
        json.append("  \"toggle_sounds\": [").append(toggles).append("],\n");
        json.append("  \"button_ticks\": [").append(buttonTicks).append("],\n");
        json.append("  \"plate_weights\": [").append(plateWeights).append("],\n");
        json.append("  \"flammable_blocks\": [").append(flammable).append("],\n");
        json.append("  \"fire_odds\": [").append(fireOdds).append("],\n");
        json.append("  \"waterloggable_blocks\": [").append(waterloggable).append("],\n");
        json.append("  \"liquid_containers\": [").append(containers).append("],\n");
        json.append("  \"dynamic_shape_blocks\": [").append(dynamic).append("],\n");
        json.append("  \"outline_differs\": [").append(outline).append("],\n");
        json.append("  \"wall_cover\": [").append(wallCover).append("],\n");
        json.append("  \"instruments\": [").append(instruments).append("],\n");
        json.append("  \"instrument_names\": [").append(instrumentNames).append("],\n");
        json.append("  \"instruments_above\": [").append(instrumentsAbove).append("],\n");
        json.append("  \"class_parents\": {").append(parentJson).append("},\n");
        json.append("  \"poi\": [").append(poi).append("],\n");
        json.append("  \"block_entities\": [").append(blockEntities).append("],\n");
        json.append("  \"turns\": [").append(turns).append("]");
        json.append(",\n  \"collision\": [").append(collision).append("],\n");
        json.append("  \"collision_boxes\": ");
        boxes(json, collisions);
        json.append(",\n  \"movement\": [").append(movement).append("],\n");
        json.append("  \"movement_boxes\": ");
        boxes(json, movements);
        json.append(",\n  \"movement_factors\": [").append(movementFactors()).append("],\n");
        json.append("  \"movement_cases\": [").append(movementCases(movements)).append("]");
        json.append(",\n  \"face_occludes\": [");
        for (int i = 0; i < faces.shapes.size(); i++) {
            json.append(i == 0 ? "[" : ", [");
            for (int j = 0; j < faces.shapes.size(); j++) {
                boolean occludes = Shapes.faceShapeOccludes(faces.shapes.get(i), faces.shapes.get(j));
                json.append(j == 0 ? "" : ", ").append(occludes ? 1 : 0);
            }
            json.append("]");
        }
        json.append("]");
        int fluidCount = fluidFaces.shapes.size();
        boolean[][] covers = new boolean[fluidCount][fluidCount];
        for (int i = 0; i < fluidCount; i++) {
            for (int j = 0; j < fluidCount; j++) {
                covers[i][j] = Shapes.mergedFaceOccludes(fluidFaces.shapes.get(i), fluidFaces.shapes.get(j), Direction.SOUTH);
            }
        }
        StringBuilder cases = new StringBuilder();
        StringBuilder offsetCases = new StringBuilder();
        List<Integer> moving = checkFluidFaces(count, fluidFaces, fluidFaceIds, covers, cases, offsetCases);
        StringBuilder movingJson = new StringBuilder();
        for (int id : moving) {
            VoxelShape moves = fluidShape(Block.BLOCK_STATE_REGISTRY.byId(id));
            movingJson.append(movingJson.isEmpty() ? "[" : ", [").append(id).append(", [");
            for (int end = 0; end < 2; end++) {
                for (Direction.Axis axis : Direction.Axis.values()) {
                    movingJson.append(end == 0 && axis == Direction.Axis.X ? "" : ", ").append(gridEnd(moves, axis, end == 1));
                }
            }
            movingJson.append("], ");
            boxesOf(movingJson, moves);
            movingJson.append("]");
        }
        // How far each block with an offset goes, which its offset function reads from it.
        Method horizontal = net.minecraft.world.level.block.state.BlockBehaviour.class.getDeclaredMethod("getMaxHorizontalOffset");
        Method vertical = net.minecraft.world.level.block.state.BlockBehaviour.class.getDeclaredMethod("getMaxVerticalOffset");
        horizontal.setAccessible(true);
        vertical.setAccessible(true);
        StringBuilder offsets = new StringBuilder();
        for (int id = 0; id < BuiltInRegistries.BLOCK.size(); id++) {
            Block block = BuiltInRegistries.BLOCK.byId(id);
            BlockState state = block.defaultBlockState();
            if (!state.hasOffsetFunction()) {
                continue;
            }
            boolean xyz = false;
            for (int i = 0; i < 64; i++) {
                xyz |= state.getOffset(new BlockPos(i * 7 - 200, 0, i * 13 - 400)).y != 0.0;
            }
            offsets.append(offsets.isEmpty() ? "[" : ", [").append(id).append(", ").append(xyz ? 1 : 0).append(", ")
                    .append(Float.floatToIntBits((float) horizontal.invoke(block))).append(", ")
                    .append(Float.floatToIntBits((float) vertical.invoke(block))).append("]");
        }
        json.append(",\n  \"fluid_faces\": [").append(fluid).append("],\n");
        json.append("  \"fluid_face_boxes\": ");
        boxes(json, fluidFaces);
        json.append(",\n  \"fluid_covers\": [");
        for (int i = 0; i < fluidCount; i++) {
            json.append(i == 0 ? "[" : ", [");
            for (int j = 0; j < fluidCount; j++) {
                json.append(j == 0 ? "" : ", ").append(covers[i][j] ? 1 : 0);
            }
            json.append("]");
        }
        json.append("],\n  \"fluid_moving\": [").append(movingJson).append("],\n");
        json.append("  \"offsets\": [").append(offsets).append("],\n");
        json.append("  \"fluid_cases\": [").append(cases).append("],\n");
        json.append("  \"offset_cases\": [").append(offsetCases).append("]\n}\n");
        Files.writeString(Path.of(args[0]), json, StandardCharsets.UTF_8);
        System.err.println("BlockFlags: wrote " + count + " states, " + faces.shapes.size() + " face shapes, "
                + collisions.shapes.size() + " collision shapes and " + fluidCount + " fluid faces to " + args[0]);
    }

    /** The state's collision shape as a fluid's wall test asks it, before vanilla offsets it by its position. */
    // A door's, trapdoor's, fence gate's, button's or pressure plate's sounds as it turns on and off,
    // or null for another block.
    private static String[] toggleSounds(Block block) throws ReflectiveOperationException {
        if (block instanceof net.minecraft.world.level.block.FenceGateBlock) {
            net.minecraft.world.level.block.state.properties.WoodType wood = (net.minecraft.world.level.block.state.properties.WoodType) fieldOf(block, "type");
            return new String[] {soundName(wood.fenceGateOpen()), soundName(wood.fenceGateClose())};
        }
        if (block instanceof net.minecraft.world.level.block.DoorBlock door) {
            return new String[] {soundName(door.type().doorOpen()), soundName(door.type().doorClose())};
        }
        if (block instanceof net.minecraft.world.level.block.TrapDoorBlock) {
            var set = (net.minecraft.world.level.block.state.properties.BlockSetType) fieldOf(block, "type");
            return new String[] {soundName(set.trapdoorOpen()), soundName(set.trapdoorClose())};
        }
        if (block instanceof net.minecraft.world.level.block.ButtonBlock) {
            var set = (net.minecraft.world.level.block.state.properties.BlockSetType) fieldOf(block, "type");
            return new String[] {soundName(set.buttonClickOn()), soundName(set.buttonClickOff())};
        }
        if (block instanceof net.minecraft.world.level.block.BasePressurePlateBlock) {
            var set = (net.minecraft.world.level.block.state.properties.BlockSetType) fieldOf(block, "type");
            return new String[] {soundName(set.pressurePlateClickOn()), soundName(set.pressurePlateClickOff())};
        }
        return null;
    }

    private static String soundName(net.minecraft.sounds.SoundEvent sound) {
        return BuiltInRegistries.SOUND_EVENT.getKey(sound).getPath();
    }

    // The field `name` of `o`, from its class or the nearest above it that declares it.
    private static Object fieldOf(Object o, String name) throws ReflectiveOperationException {
        for (Class<?> c = o.getClass(); c != null; c = c.getSuperclass()) {
            try {
                java.lang.reflect.Field f = c.getDeclaredField(name);
                f.setAccessible(true);
                return f.get(o);
            } catch (NoSuchFieldException e) {
                // Not this class's: its parent's, then.
            }
        }
        throw new NoSuchFieldException(o.getClass().getName() + "." + name);
    }

    private static VoxelShape fluidShape(BlockState state) {
        VoxelShape shape = state.getCollisionShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO);
        if (!state.hasOffsetFunction()) {
            return shape;
        }
        Vec3 offset = state.getOffset(BlockPos.ZERO);
        return shape.move(-offset.x, -offset.y, -offset.z);
    }

    // `VoxelShape.getCoords`, which `gridEnd` reads.
    private static Method coords;

    /** Where {@code shape}'s grid starts on {@code axis}, or ends if {@code last}. */
    private static double gridEnd(VoxelShape shape, Direction.Axis axis, boolean last) throws ReflectiveOperationException {
        if (coords == null) {
            coords = VoxelShape.class.getDeclaredMethod("getCoords", Direction.Axis.class);
            coords.setAccessible(true);
        }
        it.unimi.dsi.fastutil.doubles.DoubleList list = (it.unimi.dsi.fastutil.doubles.DoubleList) coords.invoke(shape, axis);
        return last ? list.getDouble(list.size() - 1) : list.getDouble(0);
    }

    /**
     * The face toward {@code d} of {@code state}, which moves, at {@code pos}, as Calcite works it
     * out: its shape before it's offset moved by its offset there, empty unless the moved shape
     * reaches that side of its block, as near as {@code mergedFaceOccludes} asks, else the boxes
     * that reach its grid's end that way, which it slices, moved, and laid flat as {@code
     * fluidFace} lays them.
     */
    private static VoxelShape movedFace(BlockState state, BlockPos pos, Direction d) throws ReflectiveOperationException {
        VoxelShape shape = fluidShape(state);
        Vec3 offset = state.getOffset(pos);
        Direction.Axis axis = d.getAxis();
        boolean positive = d.getAxisDirection() == Direction.AxisDirection.POSITIVE;
        double moved = (positive ? shape.max(axis) : shape.min(axis)) + offset.get(axis);
        if (!DoubleMath.fuzzyEquals(moved, positive ? 1.0 : 0.0, 1.0E-7)) {
            return Shapes.empty();
        }
        double end = gridEnd(shape, axis, positive);
        Direction.Axis u = axis == Direction.Axis.X ? Direction.Axis.Y : Direction.Axis.X;
        Direction.Axis v = axis == Direction.Axis.Z ? Direction.Axis.Y : Direction.Axis.Z;
        VoxelShape face = Shapes.empty();
        for (AABB box : shape.toAabbs()) {
            if ((positive ? box.max(axis) : box.min(axis)) == end) {
                face = Shapes.or(face, Shapes.box(box.min(u) + offset.get(u), box.min(v) + offset.get(v), 0.0,
                        box.max(u) + offset.get(u), box.max(v) + offset.get(v), 1.0));
            }
        }
        return face;
    }

    /**
     * The face of {@code shape} toward {@code d} as {@code Shapes.mergedFaceOccludes} slices it:
     * empty unless the shape reaches that side of its block, as near as it asks, else the boxes
     * that reach the shape's side, laid flat on the face's other two axes and one block deep along
     * z, so two faces of the same axis can be joined as {@code SOUTH} joins them.
     */
    private static VoxelShape fluidFace(VoxelShape shape, Direction d) {
        if (shape.isEmpty()) {
            return Shapes.empty();
        }
        Direction.Axis axis = d.getAxis();
        boolean positive = d.getAxisDirection() == Direction.AxisDirection.POSITIVE;
        double side = positive ? shape.max(axis) : shape.min(axis);
        if (!DoubleMath.fuzzyEquals(side, positive ? 1.0 : 0.0, 1.0E-7)) {
            return Shapes.empty();
        }
        Direction.Axis u = axis == Direction.Axis.X ? Direction.Axis.Y : Direction.Axis.X;
        Direction.Axis v = axis == Direction.Axis.Z ? Direction.Axis.Y : Direction.Axis.Z;
        VoxelShape face = Shapes.empty();
        for (AABB box : shape.toAabbs()) {
            if ((positive ? box.max(axis) : box.min(axis)) == side) {
                face = Shapes.or(face, Shapes.box(box.min(u), box.min(v), 0.0, box.max(u), box.max(v), 1.0));
            }
        }
        return face;
    }

    /**
     * Fails unless the fluid faces say what vanilla's own {@code canPassThroughWall} says. For every
     * two shapes the states have that don't move, by a state of each, each way round and toward
     * each side, the table must say it. For each state that moves, at 24 places, against a state of
     * every shape's boxes and each that moves, each way round and toward each side, its faces where
     * it is must: its boxes before they're offset, moved, as {@code fluidFace} slices them. Writes
     * the cases where moving changes the answer, and some where it doesn't, to {@code cases}, and
     * where each state that moves is offset at some places to {@code offsetCases}, and returns the
     * states that move.
     */
    private static List<Integer> checkFluidFaces(int count, Faces fluidFaces, int[][] faces, boolean[][] covers,
            StringBuilder cases, StringBuilder offsetCases) throws ReflectiveOperationException {
        Method pass = FlowingFluid.class.getDeclaredMethod("canPassThroughWall", Direction.class, BlockGetter.class,
                BlockPos.class, BlockState.class, BlockPos.class, BlockState.class);
        pass.setAccessible(true);
        Map<VoxelShape, Integer> seen = new IdentityHashMap<>();
        Map<String, Integer> boxed = new HashMap<>();
        List<Integer> shapes = new ArrayList<>();
        List<Integer> kinds = new ArrayList<>();
        List<Integer> moving = new ArrayList<>();
        for (int id = 0; id < count; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            if (state.hasOffsetFunction() && !fluidShape(state).isEmpty()) {
                if (!state.getBlock().hasDynamicShape()) {
                    throw new IllegalStateException(state + " moves with where it is, but its shape is kept as if it didn't");
                }
                moving.add(id);
                continue;
            }
            if (state.getBlock().hasDynamicShape()) {
                shapes.add(id);
            } else if (seen.putIfAbsent(state.getCollisionShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO), id) == null) {
                shapes.add(id);
            }
            VoxelShape shape = fluidShape(state);
            if (boxed.putIfAbsent(shape.isEmpty() ? "" : shape.toAabbs().toString(), id) == null) {
                kinds.add(id);
            }
        }
        long checked = 0;
        long started = System.nanoTime();
        for (int a : shapes) {
            for (int b : shapes) {
                for (Direction d : Direction.values()) {
                    BlockState first = Block.BLOCK_STATE_REGISTRY.byId(a);
                    BlockState second = Block.BLOCK_STATE_REGISTRY.byId(b);
                    boolean vanilla = (boolean) pass.invoke(null, d, EmptyBlockGetter.INSTANCE, BlockPos.ZERO, first,
                            BlockPos.ZERO.relative(d), second);
                    boolean table = !covers[faces[a][d.ordinal()]][faces[b][d.getOpposite().ordinal()]];
                    if (vanilla != table) {
                        throw new IllegalStateException("canPassThroughWall " + d + " from " + first + " to " + second
                                + " is " + vanilla + ", but the fluid faces say " + table);
                    }
                    checked++;
                }
            }
        }
        List<Integer> others = new ArrayList<>(kinds);
        others.addAll(moving);
        java.util.Set<Integer> moves = new java.util.HashSet<>(moving);
        int[] changed = new int[2];
        int kept = 0;
        for (int m : moving) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(m);
            for (int i = 0; i < 24; i++) {
                BlockPos at = new BlockPos(i * 37 - 400, i % 7 - 3, i * i * 11 - 300);
                Vec3 offset = state.getOffset(at);
                VoxelShape there = state.getCollisionShape(EmptyBlockGetter.INSTANCE, at);
                VoxelShape moved = fluidShape(state).move(offset.x, offset.y, offset.z);
                if (!there.toAabbs().toString().equals(moved.toAabbs().toString())) {
                    throw new IllegalStateException(state + " at " + at + " isn't its shape moved by its offset");
                }
                if (i < 4) {
                    offsetCases.append(offsetCases.isEmpty() ? "[" : ", [").append(m).append(", ").append(at.getX())
                            .append(", ").append(at.getZ()).append(", ").append(Double.doubleToLongBits(offset.x)).append(", ")
                            .append(Double.doubleToLongBits(offset.y)).append(", ").append(Double.doubleToLongBits(offset.z)).append("]");
                }
                for (int b : others) {
                    for (Direction d : Direction.values()) {
                        for (int way = 0; way < 2; way++) {
                            int a = way == 0 ? m : b;
                            int c = way == 0 ? b : m;
                            BlockState first = Block.BLOCK_STATE_REGISTRY.byId(a);
                            BlockState second = Block.BLOCK_STATE_REGISTRY.byId(c);
                            BlockPos to = at.relative(d);
                            boolean vanilla = (boolean) pass.invoke(null, d, EmptyBlockGetter.INSTANCE, at, first, to, second);
                            VoxelShape firstFace = moves.contains(a) ? movedFace(first, at, d)
                                    : fluidFaces.shapes.get(faces[a][d.ordinal()]);
                            VoxelShape secondFace = moves.contains(c) ? movedFace(second, to, d.getOpposite())
                                    : fluidFaces.shapes.get(faces[c][d.getOpposite().ordinal()]);
                            boolean model = !Shapes.mergedFaceOccludes(firstFace, secondFace, Direction.SOUTH);
                            if (vanilla != model) {
                                throw new IllegalStateException("canPassThroughWall " + d + " from " + first + " at " + at + " to "
                                        + second + " is " + vanilla + ", but the faces where they are say " + model);
                            }
                            boolean table = !covers[faces[a][d.ordinal()]][faces[c][d.getOpposite().ordinal()]];
                            boolean write = table != model ? changed[model ? 1 : 0] < 24 : (checked % 9973 == 0 && kept < 16);
                            if (write) {
                                if (table != model) {
                                    changed[model ? 1 : 0]++;
                                } else {
                                    kept++;
                                }
                                cases.append(cases.isEmpty() ? "[" : ", [").append(at.getX()).append(", ").append(at.getY())
                                        .append(", ").append(at.getZ()).append(", ").append(d.ordinal()).append(", ").append(a)
                                        .append(", ").append(c).append(", ").append(vanilla ? 1 : 0).append("]");
                            }
                            checked++;
                        }
                    }
                }
            }
        }
        System.err.println("BlockFlags: the fluid faces agree with canPassThroughWall " + checked + " times, over "
                + shapes.size() + " shapes and " + moving.size() + " states that move, " + (changed[0] + changed[1])
                + " of the cases written where moving changes the answer, in "
                + (System.nanoTime() - started) / 1000000 + " ms");
        return moving;
    }

    /**
     * Each block whose friction, speed factor, jump factor or bounce isn't the default, 0.6, 1, 1
     * and 0: its ID and the four floats' bits, as {@code Entity.move} reads them.
     */
    private static String movementFactors() {
        StringBuilder out = new StringBuilder();
        for (int id = 0; id < BuiltInRegistries.BLOCK.size(); id++) {
            Block block = BuiltInRegistries.BLOCK.byId(id);
            if (block.getFriction() == 0.6F && block.getSpeedFactor() == 1.0F && block.getJumpFactor() == 1.0F
                    && block.getBounceRestitution() == 0.0F) {
                continue;
            }
            out.append(out.isEmpty() ? "[" : ", [").append(id).append(", ").append(Float.floatToIntBits(block.getFriction()))
                    .append(", ").append(Float.floatToIntBits(block.getSpeedFactor())).append(", ")
                    .append(Float.floatToIntBits(block.getJumpFactor())).append(", ")
                    .append(Float.floatToIntBits(block.getBounceRestitution())).append("]");
        }
        return out.toString();
    }

    /**
     * Cases of vanilla's {@code VoxelShape.collide}, for Calcite's test: for each shape entities move
     * against, up to 8 boxes near it, an item's, a player's or a block's size, that don't overlap
     * it by more than {@code 1.0E-7}, as an entity's box doesn't while it has physics, half of them
     * resting against one of its boxes' faces, each moved along an axis by up to a block and a half
     * either way. Each is the shape, the axis, then the box's six coordinates, the distance asked and
     * the distance vanilla gives, as doubles' bits. The same seed makes the same cases each run.
     */
    private static String movementCases(Faces shapes) {
        StringBuilder out = new StringBuilder();
        java.util.Random random = new java.util.Random(148L);
        double[] widths = {0.25, 0.6, 1.0};
        double[] heights = {0.25, 1.8, 1.0};
        int total = 0;
        int moved = 0;
        for (int s = 0; s < shapes.shapes.size(); s++) {
            VoxelShape shape = shapes.shapes.get(s);
            List<AABB> parts = shape.toAabbs();
            int written = 0;
            for (int tries = 0; tries < 400 && written < 8; tries++) {
                int size = random.nextInt(3);
                double w = widths[size];
                double h = heights[size];
                double x = random.nextDouble() * 3.0 - 1.0 - w / 2;
                double y = random.nextDouble() * 3.0 - 1.0 - h / 2;
                double z = random.nextDouble() * 3.0 - 1.0 - w / 2;
                Direction.Axis axis = Direction.Axis.values()[random.nextInt(3)];
                if (!parts.isEmpty() && written % 2 == 0) {
                    // Against a face of one of its boxes, along the axis it'll move on.
                    AABB part = parts.get(random.nextInt(parts.size()));
                    boolean low = random.nextBoolean();
                    double length = axis == Direction.Axis.Y ? h : w;
                    double at = low ? part.min(axis) - length : part.max(axis);
                    if (axis == Direction.Axis.X) {
                        x = at;
                    } else if (axis == Direction.Axis.Y) {
                        y = at;
                    } else {
                        z = at;
                    }
                }
                AABB box = new AABB(x, y, z, x + w, y + h, z + w);
                if (Shapes.joinIsNotEmpty(shape, Shapes.create(box.deflate(1.0E-7)), net.minecraft.world.phys.shapes.BooleanOp.AND)) {
                    continue;
                }
                double distance = random.nextDouble() * 3.0 - 1.5;
                double given = shape.collide(axis, box, distance);
                out.append(out.isEmpty() ? "[" : ", [").append(s).append(", ").append(axis.ordinal());
                for (double v : new double[] {box.minX, box.minY, box.minZ, box.maxX, box.maxY, box.maxZ, distance, given}) {
                    out.append(", ").append(Double.doubleToLongBits(v));
                }
                out.append("]");
                written++;
                total++;
                moved += given != distance ? 1 : 0;
            }
        }
        System.err.println("BlockFlags: " + total + " collide cases over " + shapes.shapes.size() + " movement shapes, "
                + moved + " of them stopped short");
        return out.toString();
    }

    /** Each shape's boxes, as a list of lists of six numbers. */
    private static void boxes(StringBuilder json, Faces shapes) {
        json.append("[");
        for (int i = 0; i < shapes.shapes.size(); i++) {
            json.append(i == 0 ? "" : ", ");
            boxesOf(json, shapes.shapes.get(i));
        }
        json.append("]");
    }

    /** A shape's boxes, as a list of lists of six numbers. */
    private static void boxesOf(StringBuilder json, VoxelShape shape) {
        json.append("[");
        List<AABB> boxes = shape.toAabbs();
        for (int b = 0; b < boxes.size(); b++) {
            AABB box = boxes.get(b);
            json.append(b == 0 ? "[" : ", [").append(box.minX).append(", ").append(box.minY).append(", ").append(box.minZ)
                    .append(", ").append(box.maxX).append(", ").append(box.maxY).append(", ").append(box.maxZ).append("]");
        }
        json.append("]");
    }

    /** The state's collision shape with fluids, before vanilla offsets it by its position. */
    private static VoxelShape collisionShape(BlockState state) {
        VoxelShape shape = state.getCollisionShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO, CollisionContext.emptyWithFluidCollisions());
        if (!state.hasOffsetFunction()) {
            return shape;
        }
        Vec3 offset = state.getOffset(BlockPos.ZERO);
        return shape.move(-offset.x, -offset.y, -offset.z);
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
        f |= Block.isFaceFull(state.getCollisionShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO), Direction.UP) ? COLLISION_TOP_FULL : 0;
        f |= state.hasLargeCollisionShape() ? LARGE_COLLISION : 0;
        f |= state.hasOffsetFunction() ? OFFSET : 0;
        f |= state.getLightEmission() << LIGHT_EMISSION_SHIFT;
        f |= state.getLightDampening() << LIGHT_DAMPENING_SHIFT;
        return f;
    }

    /** The simple name of the class that declares the method the class runs, "" if none does. */
    private static String declaring(Class<?> type, String name, Class<?>... parameters) {
        for (Class<?> c = type; c != null && c != Object.class; c = c.getSuperclass()) {
            try {
                c.getDeclaredMethod(name, parameters);
                return c.getSimpleName();
            } catch (NoSuchMethodException e) {
                // Look further up.
            }
        }
        return "";
    }

    /**
     * What features ask of a state: whether it's solid as {@code isSolid} says, replaceable as
     * {@code canBeReplaced()} says, and so on; which of its faces are sturdy for each {@code
     * SupportType}, in {@code Direction} order; and its fluid, by its ID in the fluid registry,
     * and amount. The faces are asked at the origin of an empty world, which is where every
     * state's cache asks them; a state with no cache, whose shape changes with where it is,
     * may answer otherwise in a world.
     */
    private static long facts(BlockState state) {
        FluidState fluid = state.getFluidState();
        long f = 0;
        f |= state.isSolid() ? SOLID : 0;
        f |= state.canBeReplaced() ? REPLACEABLE : 0;
        f |= state.isCollisionShapeFullBlock(EmptyBlockGetter.INSTANCE, BlockPos.ZERO) ? COLLISION_FULL_BLOCK : 0;
        f |= state.liquid() ? LIQUID : 0;
        f |= state.ignitedByLava() ? IGNITED_BY_LAVA : 0;
        f |= state.isRedstoneConductor(EmptyBlockGetter.INSTANCE, BlockPos.ZERO) ? REDSTONE_CONDUCTOR : 0;
        for (Direction d : Direction.values()) {
            f |= state.isFaceSturdy(EmptyBlockGetter.INSTANCE, BlockPos.ZERO, d, SupportType.FULL) ? 1 << (STURDY_FULL_SHIFT + d.ordinal()) : 0;
            f |= state.isFaceSturdy(EmptyBlockGetter.INSTANCE, BlockPos.ZERO, d, SupportType.CENTER) ? 1 << (STURDY_CENTER_SHIFT + d.ordinal()) : 0;
            f |= state.isFaceSturdy(EmptyBlockGetter.INSTANCE, BlockPos.ZERO, d, SupportType.RIGID) ? 1 << (STURDY_RIGID_SHIFT + d.ordinal()) : 0;
        }
        VoxelShape collision = state.getCollisionShape(EmptyBlockGetter.INSTANCE, BlockPos.ZERO);
        for (Direction d : Direction.values()) {
            f |= Block.isFaceFull(collision, d) ? 1L << (COLLISION_FACE_SHIFT + d.ordinal()) : 0;
        }
        f |= collision.getFaceShape(Direction.UP).isEmpty() ? 0 : COLLISION_TOP_ANY & 0xFFFFFFFFL;
        f |= collision.isEmpty() ? COLLISION_EMPTY : 0;
        int type = BuiltInRegistries.FLUID.getId(fluid.getType());
        if (type < 0 || type > 7 || fluid.getAmount() > 15) {
            throw new IllegalStateException("a fluid that doesn't fit: " + fluid);
        }
        f |= (long) type << FLUID_TYPE_SHIFT;
        f |= (long) fluid.getAmount() << FLUID_AMOUNT_SHIFT;
        for (Direction d : Direction.values()) {
            f |= Block.isShapeFullBlock(state.getFaceOcclusionShape(d)) ? 1L << (OCCLUSION_FACE_SHIFT + d.ordinal()) : 0;
        }
        return f;
    }

    /**
     * The different face shapes, numbered as they're first met, each keyed by its boxes. Two
     * shapes with the same boxes cover the same space, so {@code faceShapeOccludes} treats them
     * the same; two with different boxes that happen to cover the same space just take two
     * numbers.
     */
    private static final class Faces {
        final List<VoxelShape> shapes = new ArrayList<>();
        final Map<String, Integer> ids = new HashMap<>();

        Faces() {
            id(Shapes.empty());
            id(Shapes.block());
        }

        int id(VoxelShape shape) {
            String key = shape.isEmpty() ? "" : shape.toAabbs().toString();
            Integer id = ids.get(key);
            if (id == null) {
                id = shapes.size();
                ids.put(key, id);
                shapes.add(shape);
            }
            return id;
        }
    }
}
