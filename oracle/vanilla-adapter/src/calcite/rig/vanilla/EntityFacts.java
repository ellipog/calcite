package calcite.rig.vanilla;

import java.io.IOException;
import java.io.InputStream;
import java.lang.classfile.ClassFile;
import java.lang.classfile.ClassModel;
import java.lang.classfile.CodeElement;
import java.lang.classfile.CodeModel;
import java.lang.classfile.MethodModel;
import java.lang.classfile.Opcode;
import java.lang.classfile.instruction.FieldInstruction;
import java.lang.classfile.instruction.InvokeDynamicInstruction;
import java.lang.classfile.instruction.InvokeInstruction;
import java.lang.constant.ConstantDesc;
import java.lang.constant.DirectMethodHandleDesc;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.BitSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.tags.TagKey;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EntityTypes;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.entity.SpawnPlacementType;
import net.minecraft.world.entity.SpawnPlacementTypes;
import net.minecraft.world.entity.SpawnPlacements;
import net.minecraft.world.level.EmptyBlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/**
 * Writes what natural spawning asks of each entity type and block state to the JSON file named by
 * its argument, read by oracle/datagen/calx_tables.py for src/world/entity_facts.calx. Run by
 * oracle/datagen/entity_facts.py.
 *
 * <p>For each entity type, in ID order: its category, whether it can be summoned, is fire immune,
 * can spawn far from players and is allowed in peaceful, the block tag it's immune to, the half
 * width and height of its spawn box as {@code getSpawnAABB} works them out, and where {@code
 * SpawnPlacements} registers it, its placement type, heightmap and the method its spawn rule
 * calls. The rules are read from the class file of {@code SpawnPlacements}: each {@code
 * register} call's entity type field and the method its predicate's lambda names.
 *
 * <p>For each block state: whether it's a signal source, and for which types {@code
 * isValidSpawn} holds on it, by group: the types are grouped by the states it holds on for
 * them, each group a bit. {@code isValidSpawn} reads the state's sturdy top, its light and the
 * type, not data packs, so it's the same for every world. What reads tags, as {@code
 * isBlockDangerous} does, Calcite works out with the world's tags.
 */
final class EntityFacts {
    private EntityFacts() {}

    public static void main(String[] args) throws IOException, ReflectiveOperationException {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: EntityFacts OUTPUT.json");
        }
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();
        Map<EntityType<?>, String> rules = rules();
        Field immune = EntityType.class.getDeclaredField("immuneTo");
        immune.setAccessible(true);
        int states = Block.BLOCK_STATE_REGISTRY.size();
        List<EntityType<?>> types = new ArrayList<>();
        for (EntityType<?> type : BuiltInRegistries.ENTITY_TYPE) {
            types.add(type);
        }
        // Each type's states isValidSpawn holds on, and the groups of types with the same.
        Map<BitSet, Integer> groups = new LinkedHashMap<>();
        int[] groupOf = new int[types.size()];
        for (int t = 0; t < types.size(); t++) {
            EntityType<?> type = types.get(t);
            BitSet valid = new BitSet(states);
            for (int id = 0; id < states; id++) {
                BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
                if (state.isValidSpawn(EmptyBlockGetter.INSTANCE, BlockPos.ZERO, type)) {
                    valid.set(id);
                }
            }
            Integer g = groups.get(valid);
            if (g == null) {
                g = groups.size();
                groups.put(valid, g);
            }
            groupOf[t] = g;
        }
        if (groups.size() > 30) {
            throw new IllegalStateException(groups.size() + " spawn groups, more than a state's bits hold");
        }
        StringBuilder json = new StringBuilder();
        json.append("{\n  \"game_version\": \"").append(SharedConstants.getCurrentVersion().name()).append("\",\n");
        json.append("  \"categories\": [");
        for (MobCategory category : MobCategory.values()) {
            json.append(category.ordinal() == 0 ? "\"" : ", \"").append(category.name()).append("\"");
        }
        json.append("],\n  \"types\": [");
        for (int t = 0; t < types.size(); t++) {
            EntityType<?> type = types.get(t);
            if (BuiltInRegistries.ENTITY_TYPE.getId(type) != t) {
                throw new IllegalStateException("entity type " + t + " is out of order");
            }
            AABB box = type.getSpawnAABB(0.0, 0.0, 0.0);
            TagKey<?> tag = (TagKey<?>) immune.get(type);
            json.append(t == 0 ? "\n    " : ",\n    ");
            json.append("{\"id\": \"").append(BuiltInRegistries.ENTITY_TYPE.getKey(type)).append("\"");
            json.append(", \"category\": \"").append(type.getCategory().name()).append("\"");
            json.append(", \"summon\": ").append(type.canSummon());
            json.append(", \"fire_immune\": ").append(type.fireImmune());
            json.append(", \"far\": ").append(type.canSpawnFarFromPlayer());
            json.append(", \"peaceful\": ").append(type.isAllowedInPeaceful());
            json.append(", \"immune_to\": \"").append(tag.location()).append("\"");
            json.append(", \"half_width\": ").append((float) box.maxX);
            json.append(", \"height\": ").append((float) box.maxY);
            json.append(", \"spawn_group\": ").append(groupOf[t]);
            String rule = rules.get(type);
            if (rule != null) {
                json.append(", \"placement\": \"").append(placementName(SpawnPlacements.getPlacementType(type))).append("\"");
                json.append(", \"heightmap\": \"").append(SpawnPlacements.getHeightmapType(type).name()).append("\"");
                json.append(", \"rule\": \"").append(rule).append("\"");
            }
            json.append("}");
        }
        json.append("\n  ],\n  \"spawn_groups\": ").append(groups.size()).append(",\n  \"states\": [");
        BitSet[] byGroup = groups.keySet().toArray(new BitSet[0]);
        for (int id = 0; id < states; id++) {
            BlockState state = Block.BLOCK_STATE_REGISTRY.byId(id);
            if (state == null || Block.BLOCK_STATE_REGISTRY.getId(state) != id) {
                throw new IllegalStateException("block state " + id + " is missing");
            }
            int bits = state.isSignalSource() ? 1 : 0;
            for (int g = 0; g < byGroup.length; g++) {
                if (byGroup[g].get(id)) {
                    bits |= 2 << g;
                }
            }
            json.append(id == 0 ? "" : ", ").append(bits);
        }
        json.append("]\n}\n");
        Files.writeString(Path.of(args[0]), json, StandardCharsets.UTF_8);
    }

    private static String placementName(SpawnPlacementType placement) {
        if (placement == SpawnPlacementTypes.ON_GROUND) {
            return "on_ground";
        }
        if (placement == SpawnPlacementTypes.IN_WATER) {
            return "in_water";
        }
        if (placement == SpawnPlacementTypes.IN_LAVA) {
            return "in_lava";
        }
        if (placement == SpawnPlacementTypes.NO_RESTRICTIONS) {
            return "no_restrictions";
        }
        throw new IllegalStateException("an unknown placement type: " + placement);
    }

    // Each registered type's rule, from `SpawnPlacements`' static initializer: the `EntityTypes`
    // field each `register` call is given, and the method the lambda before it names, as
    // `Owner.method`.
    private static Map<EntityType<?>, String> rules() throws IOException, ReflectiveOperationException {
        byte[] bytes;
        try (InputStream in = SpawnPlacements.class.getResourceAsStream("SpawnPlacements.class")) {
            if (in == null) {
                throw new IllegalStateException("no class file for SpawnPlacements");
            }
            bytes = in.readAllBytes();
        }
        ClassModel model = ClassFile.of().parse(bytes);
        CodeModel code = null;
        for (MethodModel m : model.methods()) {
            if (m.methodName().equalsString("<clinit>")) {
                code = m.code().orElseThrow();
            }
        }
        if (code == null) {
            throw new IllegalStateException("SpawnPlacements has no static initializer");
        }
        Map<EntityType<?>, String> out = new HashMap<>();
        String field = null;
        String rule = null;
        for (CodeElement e : code) {
            if (e instanceof FieldInstruction f && f.opcode() == Opcode.GETSTATIC
                    && f.owner().asInternalName().equals("net/minecraft/world/entity/EntityTypes")) {
                field = f.name().stringValue();
            } else if (e instanceof InvokeDynamicInstruction indy) {
                for (ConstantDesc arg : indy.bootstrapArgs()) {
                    if (arg instanceof DirectMethodHandleDesc handle) {
                        rule = handle.owner().displayName() + "." + handle.methodName();
                    }
                }
            } else if (e instanceof InvokeInstruction call && call.opcode() == Opcode.INVOKESTATIC
                    && call.name().equalsString("register")) {
                if (field == null || rule == null) {
                    throw new IllegalStateException("a register call without its type or rule");
                }
                if (rule.contains("lambda$")) {
                    throw new IllegalStateException(field + "'s rule is a lambda, not a named method: " + rule);
                }
                EntityType<?> type = (EntityType<?>) EntityTypes.class.getField(field).get(null);
                if (out.put(type, rule) != null) {
                    throw new IllegalStateException(field + " is registered twice");
                }
                field = null;
                rule = null;
            }
        }
        return out;
    }
}
