package calcite.rig.vanilla;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.entity.ai.village.poi.PoiTypes;
import net.minecraft.world.level.EmptyBlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.SupportType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.lighting.LightEngine;
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
        StringBuilder json = new StringBuilder();
        StringBuilder light = new StringBuilder();
        StringBuilder collision = new StringBuilder();
        StringBuilder facts = new StringBuilder();
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
            facts.append(id == 0 ? "" : ", ").append(facts(state));
        }
        StringBuilder poi = new StringBuilder();
        for (int id = 0; id < count; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            int type = PoiTypes.forState(state).map(h -> BuiltInRegistries.POINT_OF_INTEREST_TYPE.getId(h.value())).orElse(-1);
            if (type >= 0) {
                poi.append(poi.isEmpty() ? "[" : ", [").append(id).append(", ").append(type).append("]");
            }
        }
        StringBuilder classes = new StringBuilder();
        StringBuilder survive = new StringBuilder();
        StringBuilder placeOn = new StringBuilder();
        StringBuilder shape = new StringBuilder();
        // `FireBlock.canBurn`: the blocks fire's ignite odds are above 0 for.
        StringBuilder flammable = new StringBuilder();
        java.lang.reflect.Field igniteField = net.minecraft.world.level.block.FireBlock.class.getDeclaredField("igniteOdds");
        igniteField.setAccessible(true);
        @SuppressWarnings("unchecked")
        it.unimi.dsi.fastutil.objects.Object2IntMap<Block> ignite =
                (it.unimi.dsi.fastutil.objects.Object2IntMap<Block>) igniteField.get(net.minecraft.world.level.block.Blocks.FIRE);
        Map<String, String> parents = new java.util.TreeMap<>();
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
            if (ignite.getInt(BuiltInRegistries.BLOCK.byId(id)) > 0) {
                flammable.append(flammable.isEmpty() ? "" : ", ").append(id);
            }
            shape.append(id == 0 ? "\"" : ", \"").append(u).append("\"");
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
        json.append("  \"flammable_blocks\": [").append(flammable).append("],\n");
        json.append("  \"class_parents\": {").append(parentJson).append("},\n");
        json.append("  \"poi\": [").append(poi).append("]");
        json.append(",\n  \"collision\": [").append(collision).append("],\n");
        json.append("  \"collision_boxes\": ");
        boxes(json, collisions);
        json.append(",\n  \"face_occludes\": [");
        for (int i = 0; i < faces.shapes.size(); i++) {
            json.append(i == 0 ? "[" : ", [");
            for (int j = 0; j < faces.shapes.size(); j++) {
                boolean occludes = Shapes.faceShapeOccludes(faces.shapes.get(i), faces.shapes.get(j));
                json.append(j == 0 ? "" : ", ").append(occludes ? 1 : 0);
            }
            json.append("]");
        }
        json.append("]\n}\n");
        Files.writeString(Path.of(args[0]), json, StandardCharsets.UTF_8);
        System.err.println("BlockFlags: wrote " + count + " states, " + faces.shapes.size() + " face shapes and "
                + collisions.shapes.size() + " collision shapes to " + args[0]);
    }

    /** Each shape's boxes, as a list of lists of six numbers. */
    private static void boxes(StringBuilder json, Faces shapes) {
        json.append("[");
        for (int i = 0; i < shapes.shapes.size(); i++) {
            json.append(i == 0 ? "[" : ", [");
            List<AABB> boxes = shapes.shapes.get(i).toAabbs();
            for (int b = 0; b < boxes.size(); b++) {
                AABB box = boxes.get(b);
                json.append(b == 0 ? "[" : ", [").append(box.minX).append(", ").append(box.minY).append(", ").append(box.minZ)
                        .append(", ").append(box.maxX).append(", ").append(box.maxY).append(", ").append(box.maxZ).append("]");
            }
            json.append("]");
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
