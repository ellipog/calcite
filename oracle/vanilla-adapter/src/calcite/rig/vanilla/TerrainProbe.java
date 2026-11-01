package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;
import it.unimi.dsi.fastutil.shorts.ShortList;
import net.minecraft.IdentifierException;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.NoiseColumn;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.biome.FixedBiomeSource;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.levelgen.Aquifer;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseChunk;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.NoiseSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.blending.Blender;
import net.minecraft.world.level.levelgen.densityfunction.DensityVolume;

/**
 * `terrain`: a noise settings' terrain shape, as {@code NoiseBasedChunkGenerator} fills a chunk
 * before its surface and carvers (its final density through the aquifer, into the sections, the
 * two `_WG` heightmaps and the blocks marked for post-processing), and as it gives a column's
 * base blocks and heights.
 *
 * <p>A fill does what {@code buildTerrain} does before {@code buildSurface}: it makes the
 * generator's {@code NoiseChunk}, with no structures to beardify, and runs its {@code doFill}.
 */
final class TerrainProbe implements Probe {
    private static final long MAX_VALUES = 1L << 22;
    private static final Heightmap.Types[] KINDS = Heightmap.Types.values();
    private static final Field FLUID_PICKER = field(NoiseBasedChunkGenerator.class, "globalFluidPicker");
    private static final Field COLUMN_MIN_Y = field(NoiseColumn.class, "minY");
    private static final Field COLUMN = field(NoiseColumn.class, "column");
    private static final Method CHUNK_VOLUME = method("chunkVolume", ChunkAccess.class, NoiseSettings.class);
    private static final Method DO_FILL = method("doFill", NoiseChunk.class, ChunkAccess.class);

    @Override
    public String name() {
        return "terrain";
    }

    @Override
    public int version() {
        return 1;
    }

    private static Field field(Class<?> owner, String name) {
        try {
            Field f = owner.getDeclaredField(name);
            f.setAccessible(true);
            return f;
        } catch (NoSuchFieldException e) {
            throw new IllegalStateException(owner.getSimpleName() + " has no " + name, e);
        }
    }

    private static Method method(String name, Class<?>... parameters) {
        try {
            Method m = NoiseBasedChunkGenerator.class.getDeclaredMethod(name, parameters);
            m.setAccessible(true);
            return m;
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException("NoiseBasedChunkGenerator has no " + name, e);
        }
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        if (!blobs.isEmpty()) {
            throw new CaseError("`terrain` takes no blobs");
        }
        RegistryAccess.Frozen access = RegistriesProbe.access();
        long seed = Args.int64(input, "seed");
        Identifier id;
        try {
            id = Identifier.parse(Args.string(input, "settings"));
        } catch (IdentifierException e) {
            throw new CaseError("`settings` must be an identifier");
        }
        Holder<NoiseGeneratorSettings> settings = access.lookupOrThrow(Registries.NOISE_SETTINGS)
                .get(ResourceKey.create(Registries.NOISE_SETTINGS, id))
                .orElseThrow(() -> new CaseError("no noise settings `" + id + "`"));
        JsonArray level = Args.array(input, "level");
        if (level.size() != 2) {
            throw new CaseError("`level` must be [min_y, height]");
        }
        int minY = Args.asInt(level.get(0), "`level`[0]");
        int height = Args.asInt(level.get(1), "`level`[1]");
        if (minY % 16 != 0 || height % 16 != 0 || height <= 0 || minY < -2032 || minY + height > 2032) {
            throw new CaseError("`level` must be whole sections within the world");
        }
        JsonArray opList = Args.array(input, "ops");
        List<JsonArray> steps = new ArrayList<>();
        long values = 0;
        for (int i = 0; i < opList.size(); i++) {
            String what = "`ops`[" + i + "]";
            if (!opList.get(i).isJsonArray() || opList.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError(what + " must be a non-empty array");
            }
            JsonArray op = opList.get(i).getAsJsonArray();
            String kind = Args.asString(op.get(0), what + "[0]");
            switch (kind) {
                case "fill" -> values += 256L * height;
                case "column" -> values += height;
                default -> throw new CaseError(what + ": unknown op `" + kind + "`");
            }
            if (op.size() != 3) {
                throw new CaseError(what + " must have 3 elements");
            }
            Args.asInt(op.get(1), what + "[1]");
            Args.asInt(op.get(2), what + "[2]");
            steps.add(op);
        }
        if (values > MAX_VALUES) {
            throw new CaseError("the ops give more than " + MAX_VALUES + " values");
        }
        NoiseBasedChunkGenerator generator = new NoiseBasedChunkGenerator(
                new FixedBiomeSource(access.lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS)), settings);
        LevelHeightAccessor heights = LevelHeightAccessor.create(minY, height);
        PalettedContainerFactory containers = PalettedContainerFactory.create(access);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        try {
            RandomState state = RandomState.create(access.lookupOrThrow(Registries.NOISE), seed, settings.value());
            for (JsonArray op : steps) {
                int a = op.get(1).getAsInt();
                int b = op.get(2).getAsInt();
                if (op.get(0).getAsString().equals("fill")) {
                    fill(generator, settings.value(), state, new ProtoChunk(new ChunkPos(a, b), UpgradeData.EMPTY, heights, containers, null), out);
                } else {
                    column(generator, state, heights, a, b, out);
                }
            }
        } catch (CaseError e) {
            throw e;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        } catch (RuntimeException e) {
            return Result.rejected(e);
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    /** {@code buildTerrain}'s fill, then the chunk's blocks, `_WG` heightmaps and marked blocks. */
    private static void fill(NoiseBasedChunkGenerator generator, NoiseGeneratorSettings settings, RandomState state, ProtoChunk chunk, DataOutputStream out)
            throws IOException {
        NoiseSettings noise = settings.noiseSettings().clampToHeightAccessor(chunk.getHeightAccessorForGeneration());
        if (noise.height() > 0) {
            try (NoiseChunk noiseChunk = new NoiseChunk(
                    state, null, settings, fluidPicker(generator), Blender.empty(), (DensityVolume) invoke(CHUNK_VOLUME, null, chunk, noise))) {
                invoke(DO_FILL, generator, noiseChunk, chunk);
            }
        }
        // The blocks as runs of one state, from the bottom up, each section in y, z, x order.
        List<int[]> runs = new ArrayList<>();
        BlockPos.MutableBlockPos pos = new BlockPos.MutableBlockPos();
        for (int y = chunk.getMinY(); y <= chunk.getMaxY(); y++) {
            for (int z = 0; z < 16; z++) {
                for (int x = 0; x < 16; x++) {
                    int id = Block.BLOCK_STATE_REGISTRY.getId(chunk.getBlockState(pos.set(x, y, z)));
                    if (!runs.isEmpty() && runs.getLast()[0] == id) {
                        runs.getLast()[1]++;
                    } else {
                        runs.add(new int[] {id, 1});
                    }
                }
            }
        }
        out.writeInt(runs.size());
        for (int[] run : runs) {
            out.writeInt(run[0]);
            out.writeInt(run[1]);
        }
        for (Heightmap.Types kind : List.of(Heightmap.Types.OCEAN_FLOOR_WG, Heightmap.Types.WORLD_SURFACE_WG)) {
            Heightmap heightmap = chunk.getOrCreateHeightmapUnprimed(kind);
            for (int z = 0; z < 16; z++) {
                for (int x = 0; x < 16; x++) {
                    out.writeInt(heightmap.getFirstAvailable(x, z));
                }
            }
        }
        ShortList[] marked = chunk.getPostProcessing();
        for (ShortList list : marked) {
            out.writeInt(list == null ? 0 : list.size());
            if (list != null) {
                for (int i = 0; i < list.size(); i++) {
                    out.writeInt(list.getShort(i));
                }
            }
        }
    }

    /** {@code getBaseColumn}'s blocks, from the bottom up, then each heightmap's {@code getBaseHeight}. */
    private static void column(NoiseBasedChunkGenerator generator, RandomState state, LevelHeightAccessor heights, int x, int z, DataOutputStream out)
            throws IOException {
        NoiseColumn column = generator.getBaseColumn(x, z, heights, state);
        if (column == null) {
            out.writeInt(-1);
        } else {
            BlockState[] states = (BlockState[]) get(COLUMN, column);
            out.writeInt(states.length);
            out.writeInt((int) get(COLUMN_MIN_Y, column));
            for (BlockState s : states) {
                out.writeInt(Block.BLOCK_STATE_REGISTRY.getId(s));
            }
        }
        for (Heightmap.Types kind : KINDS) {
            out.writeInt(generator.getBaseHeight(x, z, kind, heights, state));
        }
    }

    @SuppressWarnings("unchecked")
    private static Aquifer.FluidPicker fluidPicker(NoiseBasedChunkGenerator generator) {
        return ((Supplier<Aquifer.FluidPicker>) get(FLUID_PICKER, generator)).get();
    }

    private static Object get(Field f, Object owner) {
        try {
            return f.get(owner);
        } catch (IllegalAccessException e) {
            throw new IllegalStateException(e);
        }
    }

    private static Object invoke(Method m, Object owner, Object... arguments) {
        try {
            return m.invoke(owner, arguments);
        } catch (IllegalAccessException e) {
            throw new IllegalStateException(e);
        } catch (InvocationTargetException e) {
            if (e.getCause() instanceof RuntimeException r) {
                throw r;
            }
            throw new IllegalStateException(e.getCause());
        }
    }
}
