package calcite.rig.vanilla;

import com.google.gson.JsonObject;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.TagParser;
import net.minecraft.resources.Identifier;
import net.minecraft.util.ProblemReporter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.TagValueInput;

/**
 * `block_entity`: a block entity loaded from data and saved again, as a structure template's are
 * when it places them: `loadWithComponents` of the data, then what `saveAdditional` writes
 * (`saveCustomOnly`). The block entity is new, at the origin, in the first block its type is valid
 * for, with no level, as one in a chunk that's still generating has none.
 */
final class BlockEntityProbe implements Probe {
    @Override
    public String name() {
        return "block_entity";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        String id = Args.string(input, "id");
        BlockEntityType<?> type = BuiltInRegistries.BLOCK_ENTITY_TYPE.getOptional(Identifier.parse(id))
            .orElseThrow(() -> new CaseError("unknown block entity type `" + id + "`"));
        BlockState state = BuiltInRegistries.BLOCK.stream()
            .map(Block::defaultBlockState)
            .filter(type::isValid)
            .findFirst()
            .orElseThrow(() -> new CaseError("no block for `" + id + "`"));
        CompoundTag tag;
        try {
            tag = TagParser.parseCompoundFully(Args.string(input, "snbt"));
        } catch (Exception e) {
            throw new CaseError("`snbt` doesn't parse: " + e.getMessage());
        }
        RegistryAccess access = RegistriesProbe.access();
        BlockEntity entity = type.create(BlockPos.ZERO, state);
        entity.loadWithComponents(TagValueInput.create(ProblemReporter.DISCARDING, access, tag));
        JsonObject output = new JsonObject();
        output.addProperty("snbt", entity.saveCustomOnly(access).toString());
        return Result.ok(output);
    }
}
