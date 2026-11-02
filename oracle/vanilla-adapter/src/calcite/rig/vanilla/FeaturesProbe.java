package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.JsonOps;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import it.unimi.dsi.fastutil.objects.ObjectOpenHashSet;
import net.minecraft.IdentifierException;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.dedicated.DedicatedServer;
import net.minecraft.server.level.ServerChunkCache;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.WorldGenRegion;
import net.minecraft.util.StaticCache2D;
import net.minecraft.world.Difficulty;
import net.minecraft.world.attribute.EnvironmentAttributeSystem;
import net.minecraft.world.entity.ai.village.poi.PoiType;
import net.minecraft.world.entity.ai.village.poi.PoiTypes;
import net.minecraft.world.flag.FeatureFlagSet;
import net.minecraft.world.flag.FeatureFlags;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.chunk.LightChunk;
import net.minecraft.world.level.chunk.LightChunkGetter;
import net.minecraft.world.level.lighting.LevelLightEngine;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeManager;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.chunk.ChunkGeneratorStructureState;
import net.minecraft.world.level.chunk.PalettedContainerFactory;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.chunk.status.ChunkPyramid;
import net.minecraft.world.level.chunk.status.ChunkStatus;
import net.minecraft.world.level.dimension.BuiltinDimensionTypes;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.level.levelgen.Beardifier;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseChunk;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.NoiseSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.WorldGenerationContext;
import net.minecraft.world.level.levelgen.WorldOptions;
import net.minecraft.world.level.levelgen.WorldgenRandom;
import net.minecraft.world.level.levelgen.XoroshiroRandomSource;
import net.minecraft.world.level.levelgen.blending.Blender;
import net.minecraft.world.level.levelgen.densityfunction.SamplerContext;
import net.minecraft.world.level.levelgen.material.rule.MaterialRule;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplateManager;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.util.datafix.DataFixers;
import net.minecraft.core.HolderGetter;
import net.minecraft.world.level.material.Fluid;
import net.minecraft.world.level.storage.LevelData;
import net.minecraft.world.ticks.ProtoChunkTicks;
import net.minecraft.world.ticks.SavedTick;

/**
 * `features`: chunks decorated as {@code ChunkGenerator.applyBiomeDecoration} decorates them in
 * 26.3, or one placed feature placed, in a {@code WorldGenRegion} over chunks the probe makes
 * (rig/PROTOCOL.md).
 *
 * <p>For an op at a chunk, the 5×5 chunks around it get their biomes as {@code createBiomes}
 * gives them, and the 3×3 around it their terrain, each as the `carvers` probe makes its chunk,
 * with the settings' own rule and its biomes' carvers, and are marked done with {@code terrain}.
 * The region is vanilla's own class, made field by field as its constructor would make it for
 * the {@code features} step, since its constructor wants holders the probe doesn't have: its
 * cache holds those chunks and, out to 8 away, empty chunks marked done with
 * {@code structure_starts}, as a server holds them. Its level is a stand-in for a
 * {@code ServerLevel}, made without its constructor, that notes the point-of-interest changes
 * the region tells it of. Structures don't generate: the probe's structure manager says so.
 *
 * <p>A `structured` op decorates with structures. The chunks out to 9 around get their starts, as
 * the `structures` probe's `bearded` op makes them, and each of the 3×3 its references and its
 * terrain filled with their beardifier. The region's chunks are given those starts, and the 3×3
 * their references, and the structure manager says structures generate. Entities are written
 * only as their type, position and rotation, since the rest of what an entity saves is random
 * or set as it's spawned.
 */
final class FeaturesProbe implements Probe {
    private static final long MAX_CHUNKS = 64;
    private static final Method GENERATE_CARVERS = TerrainProbe.method(
            "generateCarvers",
            ChunkAccess.class,
            Blender.class,
            NoiseChunk.class,
            RandomState.class,
            BiomeManager.class,
            WorldGenRegion.class,
            MaterialRule.class);
    private static final Heightmap.Types[] FINAL = {
        Heightmap.Types.WORLD_SURFACE, Heightmap.Types.OCEAN_FLOOR, Heightmap.Types.MOTION_BLOCKING, Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
    };

    @Override
    public String name() {
        return "features";
    }

    @Override
    public int version() {
        return 4;
    }

    /** The level, as far as the region and features ask it. */
    private static final class Level extends ServerLevel {
        Source source;
        DimensionType type;
        RegistryAccess registries;
        int minY;
        int height;
        int seaLevel;
        List<int[]> poi;
        LevelLightEngine light;
        MinecraftServer server;
        long seed;
        StructureManager structures;
        EnvironmentAttributeSystem attributes;

        // Never run: the level is made with `Unsafe.allocateInstance`.
        private Level() {
            super(null, null, null, null, null, null, false, 0L, null, false);
        }

        @Override
        public DimensionType dimensionType() {
            return type;
        }

        @Override
        public ServerChunkCache getChunkSource() {
            return source;
        }

        // An entity's network ID, which a feature's entity is made with and which isn't saved.
        @Override
        public int getNextEntityId() {
            return 1;
        }

        @Override
        public RegistryAccess registryAccess() {
            return registries;
        }

        @Override
        public MinecraftServer getServer() {
            return server;
        }

        @Override
        public FeatureFlagSet enabledFeatures() {
            return FeatureFlags.DEFAULT_FLAGS;
        }

        @Override
        public int getMinY() {
            return minY;
        }

        @Override
        public int getHeight() {
            return height;
        }

        @Override
        public int getSeaLevel() {
            return seaLevel;
        }

        // The level's data, as the region's: what a structure's mob asks as it's made.
        @Override
        public LevelData getLevelData() {
            return DATA;
        }

        // The world's seed, which a capped processor seeds its random from.
        @Override
        public long getSeed() {
            return seed;
        }

        // The decoration's structure manager, over the region's chunks, which are those of the
        // chunk being decorated and around it: where a cat asks whether it's in a swamp hut.
        @Override
        public StructureManager structureManager() {
            return structures;
        }

        // The region's attributes, the dimension's and its biomes': what a villager's schedule
        // reads as it's made.
        @Override
        public EnvironmentAttributeSystem environmentAttributes() {
            return attributes;
        }

        // A new world's clock, at 0 with a full moon: what a structure's mob's difficulty reads.
        @Override
        public long getOverworldClockTime() {
            return 0L;
        }

        @Override
        public float getMoonBrightness(BlockPos pos) {
            return DimensionType.MOON_BRIGHTNESS_PER_PHASE[0];
        }

        /**
         * A light engine with no sections, as the server's is for chunks not yet lit: the sky
         * light is 15 wherever the dimension has one, and the block light 0.
         */
        @Override
        public LevelLightEngine getLightEngine() {
            return light;
        }

        @Override
        public void updatePOIOnBlockStateChange(BlockPos pos, BlockState oldState, BlockState newState) {
            Optional<Holder<PoiType>> oldType = PoiTypes.forState(oldState);
            Optional<Holder<PoiType>> newType = PoiTypes.forState(newState);
            if (!oldType.equals(newType)) {
                poi.add(new int[] {pos.getX(), pos.getY(), pos.getZ(), poiId(oldType), poiId(newType)});
            }
        }

        private static int poiId(Optional<Holder<PoiType>> type) {
            return type.map(t -> BuiltInRegistries.POINT_OF_INTEREST_TYPE.getId(t.value())).orElse(-1);
        }
    }

    /** The chunk source, for the random state and the generator. */
    private static final class Source extends ServerChunkCache {
        RandomState state;
        ChunkGenerator generator;

        // Never run, as the level's.
        private Source() {
            super(null, null, null, null, null, null, 0, 0, false, null);
        }

        @Override
        public RandomState randomState() {
            return state;
        }

        @Override
        public ChunkGenerator getGenerator() {
            return generator;
        }
    }

    /**
     * The server's structure templates, as its {@code StructureTemplateManager} loads them from
     * the vanilla data pack: {@code data/<namespace>/structure/<path>.nbt} read with
     * {@code NbtIo.readCompressed}, upgraded from its data version and loaded with the block
     * registry. One that isn't there is an empty template, as {@code getOrCreate} makes it.
     */
    static final class Templates extends StructureTemplateManager {
        Map<Identifier, Optional<StructureTemplate>> loaded;
        HolderGetter<Block> blocks;

        // Never run, as the level's.
        private Templates() {
            super(null, null, null, null);
        }

        @Override
        public StructureTemplate getOrCreate(Identifier id) {
            Optional<StructureTemplate> found = get(id);
            if (found.isPresent()) {
                return found.get();
            }
            StructureTemplate made = new StructureTemplate();
            loaded.put(id, Optional.of(made));
            return made;
        }

        @Override
        public Optional<StructureTemplate> get(Identifier id) {
            return loaded.computeIfAbsent(id, this::load);
        }

        private Optional<StructureTemplate> load(Identifier id) {
            String path = "data/" + id.getNamespace() + "/structure/" + id.getPath() + ".nbt";
            try (InputStream in = FeaturesProbe.class.getClassLoader().getResourceAsStream(path)) {
                if (in == null) {
                    return Optional.empty();
                }
                CompoundTag tag = NbtIo.readCompressed(in, NbtAccounter.unlimitedHeap());
                int version = NbtUtils.getDataVersion(tag, 500);
                StructureTemplate template = new StructureTemplate();
                template.load(blocks, DataFixTypes.STRUCTURE.updateToCurrentVersion(DataFixers.getDataFixer(), tag, version));
                return Optional.of(template);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        // A parameter list's search remembers its last result per thread, so each case runs on
        // a thread of its own, from no last result.
        Result[] result = new Result[1];
        Throwable[] thrown = new Throwable[1];
        Thread thread = new Thread(() -> {
            try {
                result[0] = runCase(input, blobs);
            } catch (Throwable e) {
                thrown[0] = e;
            }
        }, "features case");
        thread.start();
        try {
            thread.join();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
        if (thrown[0] instanceof RuntimeException e) {
            throw e;
        }
        if (thrown[0] != null) {
            throw new IllegalStateException("the case threw", thrown[0]);
        }
        return result[0];
    }

    private Result runCase(JsonObject input, List<byte[]> blobs) throws Exception {
        if (!blobs.isEmpty()) {
            throw new CaseError("`features` takes no blobs");
        }
        RegistryAccess.Frozen access = RegistriesProbe.access();
        RegistryOps<JsonElement> ops = access.createSerializationContext(JsonOps.INSTANCE);
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
        List<long[]> steps = new ArrayList<>();
        if (opList.size() > MAX_CHUNKS) {
            throw new CaseError("at most " + MAX_CHUNKS + " ops");
        }
        boolean places = false;
        // Shared: the ops' chunks are one world's, each op's decoration writing into the chunks the
        // ops before it left, in the order they're given.
        boolean shared = false;
        if (input.has("shared")) {
            JsonElement value = input.get("shared");
            if (!value.isJsonPrimitive() || !value.getAsJsonPrimitive().isBoolean()) {
                throw new CaseError("`shared` must be a boolean");
            }
            shared = value.getAsBoolean();
        }
        Map<Long, ProtoChunk> world = shared ? new HashMap<>() : null;
        for (int i = 0; i < opList.size(); i++) {
            String what = "`ops`[" + i + "]";
            if (!opList.get(i).isJsonArray() || opList.get(i).getAsJsonArray().isEmpty()) {
                throw new CaseError(what + " must be a non-empty array");
            }
            JsonArray op = opList.get(i).getAsJsonArray();
            String kind = Args.asString(op.get(0), what + "[0]");
            if (kind.equals("decorate")) {
                if (op.size() != 3) {
                    throw new CaseError(what + " must have 3 elements");
                }
                steps.add(new long[] {0, Args.asInt(op.get(1), what + "[1]"), Args.asInt(op.get(2), what + "[2]")});
            } else if (kind.equals("structured")) {
                if (op.size() != 3) {
                    throw new CaseError(what + " must have 3 elements");
                }
                steps.add(new long[] {2, Args.asInt(op.get(1), what + "[1]"), Args.asInt(op.get(2), what + "[2]")});
            } else if (kind.equals("place")) {
                if (op.size() != 7) {
                    throw new CaseError(what + " must have 7 elements");
                }
                int cx = Args.asInt(op.get(1), what + "[1]");
                int cz = Args.asInt(op.get(2), what + "[2]");
                int x = Args.asInt(op.get(3), what + "[3]");
                int y = Args.asInt(op.get(4), what + "[4]");
                int z = Args.asInt(op.get(5), what + "[5]");
                long featureSeed = Args.parseLong(Args.asString(op.get(6), what + "[6]"), what + "[6]");
                steps.add(new long[] {1, cx, cz, x, y, z, featureSeed});
                places = true;
            } else {
                throw new CaseError(what + ": unknown op `" + kind + "`");
            }
        }
        // A source or feature that doesn't read is compared only as that: the codecs' messages
        // are their own.
        var parsedSource = BiomeSource.CODEC.parse(ops, Args.field(input, "source"));
        if (parsedSource.isError()) {
            return invalid("source");
        }
        BiomeSource source = parsedSource.getOrThrow();
        Holder<PlacedFeature> feature = null;
        if (input.has("feature")) {
            DataResult<Holder<PlacedFeature>> parsed = PlacedFeature.CODEC.parse(ops, input.get("feature"));
            if (parsed.isError()) {
                System.err.println("features: the feature doesn't read: " + parsed.error().orElseThrow().message());
                return invalid("feature");
            }
            feature = parsed.getOrThrow();
        } else if (places) {
            throw new CaseError("a `place` op needs `feature`");
        }
        NoiseBasedChunkGenerator generator = new NoiseBasedChunkGenerator(source, settings);
        LevelHeightAccessor heights = LevelHeightAccessor.create(minY, height);
        PalettedContainerFactory containers = PalettedContainerFactory.create(access);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        try {
            RandomState state = RandomState.create(access.lookupOrThrow(Registries.NOISE), seed, settings.value());
            Level fake = (Level) allocate(Level.class);
            fake.source = (Source) allocate(Source.class);
            fake.source.state = state;
            fake.source.generator = generator;
            fake.type = dimensionType(access, id);
            fake.registries = access;
            fake.seed = seed;
            // A server, made without its constructor, whose only part features ask for is its
            // structure templates.
            Templates templates = (Templates) allocate(Templates.class);
            templates.loaded = new HashMap<>();
            templates.blocks = access.lookupOrThrow(Registries.BLOCK);
            fake.server = (MinecraftServer) allocate(DedicatedServer.class);
            Field templateField = MinecraftServer.class.getDeclaredField("structureTemplateManager");
            templateField.setAccessible(true);
            templateField.set(fake.server, templates);
            fake.minY = minY;
            fake.height = height;
            fake.seaLevel = generator.getSeaLevel();
            fake.light = new LevelLightEngine(new LightChunkGetter() {
                @Override
                public LightChunk getChunkForLighting(int x, int z) {
                    return null;
                }

                @Override
                public BlockGetter getLevel() {
                    return fake;
                }
            }, true, fake.type.hasSkyLight());
            ChunkGeneratorStructureState structureState = null;
            for (long[] op : steps) {
                fake.poi = new ArrayList<>();
                int cx = (int) op[1];
                int cz = (int) op[2];
                Map<Long, ProtoChunk> starts = null;
                Map<Long, Beardifier> beards = new HashMap<>();
                if (op[0] == 2) {
                    if (structureState == null) {
                        structureState = generator.createState(access.lookupOrThrow(Registries.STRUCTURE_SET), state, seed);
                    }
                    ResourceKey<net.minecraft.world.level.Level> dimension = id.getPath().equals("nether")
                            ? net.minecraft.world.level.Level.NETHER
                            : id.getPath().equals("end") ? net.minecraft.world.level.Level.END : net.minecraft.world.level.Level.OVERWORLD;
                    starts = StructuresProbe.startsAround(access, generator, structureState, templates, dimension, heights, containers, new ChunkPos(cx, cz), 9);
                    StructureManager startsManager = StructuresProbe.manager(starts);
                    for (int dz = -1; dz <= 1; dz++) {
                        for (int dx = -1; dx <= 1; dx++) {
                            ProtoChunk withStarts = starts.get(ChunkPos.pack(cx + dx, cz + dz));
                            StructuresProbe.references(access, generator, startsManager, withStarts);
                            beards.put(withStarts.getPos().pack(), Beardifier.forStructuresInChunk(startsManager, withStarts.getPos()));
                        }
                    }
                }
                Map<Long, ProtoChunk> chunks = terrain(generator, settings.value(), state, source, seed, heights, containers, cx, cz, beards, world);
                WorldGenRegion region = region(fake, chunks, generator, source, state, seed, heights, containers, cx, cz, starts);
                ProtoChunk center = chunks.get(ChunkPos.pack(cx, cz));
                if (op[0] == 0) {
                    StructureManager structures = new StructureManager(region, new WorldOptions(seed, false, false), null);
                    fake.structures = structures;
                    generator.applyBiomeDecoration(region, center, structures);
                } else if (op[0] == 2) {
                    for (int dz = -1; dz <= 1; dz++) {
                        for (int dx = -1; dx <= 1; dx++) {
                            long key = ChunkPos.pack(cx + dx, cz + dz);
                            chunks.get(key).setAllStarts(starts.get(key).getAllStarts());
                            chunks.get(key).setAllReferences(starts.get(key).getAllReferences());
                        }
                    }
                    StructureManager structures = new StructureManager(region, new WorldOptions(seed, true, false), null);
                    fake.structures = structures;
                    generator.applyBiomeDecoration(region, center, structures);
                } else {
                    WorldgenRandom random = new WorldgenRandom(new XoroshiroRandomSource(0L));
                    random.setSeed(op[6]);
                    feature.value().place(region, generator, random, new BlockPos((int) op[3], (int) op[4], (int) op[5]));
                }
                for (int dz = -1; dz <= 1; dz++) {
                    for (int dx = -1; dx <= 1; dx++) {
                        write(chunks.get(ChunkPos.pack(cx + dx, cz + dz)), access, out, op[0] == 2);
                    }
                }
                out.writeInt(fake.poi.size());
                for (int[] p : fake.poi) {
                    for (int v : p) {
                        out.writeInt(v);
                    }
                }
            }
        } catch (CaseError e) {
            throw e;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        } catch (RuntimeException e) {
            // Only to the log: where it threw.
            e.printStackTrace();
            return Result.rejected(e);
        }
        return Result.ok(new JsonObject(), bytes.toByteArray());
    }

    private static Result invalid(String what) {
        JsonObject invalid = new JsonObject();
        invalid.addProperty("invalid", what);
        return Result.ok(invalid);
    }

    /** The dimension type the settings' world has: the Nether's or the End's, or the Overworld's. */
    static DimensionType dimensionType(RegistryAccess access, Identifier settings) {
        ResourceKey<DimensionType> key = settings.getPath().equals("nether")
                ? BuiltinDimensionTypes.NETHER
                : settings.getPath().equals("end") ? BuiltinDimensionTypes.END : BuiltinDimensionTypes.OVERWORLD;
        return access.lookupOrThrow(Registries.DIMENSION_TYPE).getOrThrow(key).value();
    }

    /**
     * The 5×5 chunks around {@code cx}, {@code cz} with their biomes, and the 3×3 with their
     * terrain, marked done with {@code terrain}. With a {@code world}, a chunk it has is taken as
     * it is, and each of the 3×3 is kept in it.
     */
    private static Map<Long, ProtoChunk> terrain(
            NoiseBasedChunkGenerator generator,
            NoiseGeneratorSettings settings,
            RandomState state,
            BiomeSource source,
            long seed,
            LevelHeightAccessor heights,
            PalettedContainerFactory containers,
            int cx,
            int cz,
            Map<Long, Beardifier> beards,
            Map<Long, ProtoChunk> world) {
        Map<Long, ProtoChunk> chunks = new HashMap<>();
        for (int dz = -2; dz <= 2; dz++) {
            for (int dx = -2; dx <= 2; dx++) {
                ChunkPos pos = new ChunkPos(cx + dx, cz + dz);
                if (world != null && world.containsKey(pos.pack())) {
                    chunks.put(pos.pack(), world.get(pos.pack()));
                    continue;
                }
                ProtoChunk chunk = new ProtoChunk(pos, UpgradeData.EMPTY, heights, containers, null);
                Climate.Sampler climate = state.createClimateSampler(SamplerContext.builder().enableCaches().build());
                chunk.fillBiomesFromNoise(source.createResolverForChunk(
                        climate,
                        QuartPos.fromBlock(pos.getMinBlockX()),
                        QuartPos.fromBlock(chunk.getMinY()),
                        QuartPos.fromBlock(pos.getMinBlockZ()),
                        QuartPos.fromBlock(16),
                        QuartPos.fromBlock(chunk.getHeight()),
                        QuartPos.fromBlock(16)));
                chunk.setPersistedStatus(ChunkStatus.BIOMES);
                chunks.put(pos.pack(), chunk);
            }
        }
        MaterialRule rule = settings.materialRule().value();
        for (int dz = -1; dz <= 1; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                int x = cx + dx;
                int z = cz + dz;
                ProtoChunk chunk = chunks.get(ChunkPos.pack(x, z));
                if (world != null && world.containsKey(ChunkPos.pack(x, z))) {
                    continue;
                }
                Set<Holder<Biome>> possibleBiomes = new ObjectOpenHashSet<>();
                for (int nz = -1; nz <= 1; nz++) {
                    for (int nx = -1; nx <= 1; nx++) {
                        chunks.get(ChunkPos.pack(x + nx, z + nz)).collectBiomesInPalette(possibleBiomes);
                    }
                }
                BiomeManager biomes = new BiomeManager((quartX, quartY, quartZ) -> {
                    int sx = QuartPos.toSection(quartX);
                    int sz = QuartPos.toSection(quartZ);
                    if (Math.abs(sx - x) > 1 || Math.abs(sz - z) > 1) {
                        throw new IllegalStateException("a biome outside the chunk's neighbours");
                    }
                    return chunks.get(ChunkPos.pack(sx, sz)).getNoiseBiome(quartX, quartY, quartZ);
                }, BiomeManager.obfuscateSeed(seed));
                NoiseSettings noise = settings.noiseSettings().clampToHeightAccessor(chunk.getHeightAccessorForGeneration());
                if (noise.height() > 0) {
                    try (NoiseChunk noiseChunk = TerrainProbe.noiseChunk(generator, settings, state, chunk, noise, beards.get(ChunkPos.pack(x, z)))) {
                        TerrainProbe.doFill(generator, noiseChunk, chunk);
                        WorldGenerationContext context = new WorldGenerationContext(generator, chunk.getHeightAccessorForGeneration());
                        state.surfaceSystem().buildSurface(state, biomes, context, chunk, noiseChunk, rule, possibleBiomes);
                        TerrainProbe.invoke(GENERATE_CARVERS, generator, chunk, Blender.empty(), noiseChunk, state, biomes, null, rule);
                    }
                }
            }
        }
        for (int dz = -1; dz <= 1; dz++) {
            for (int dx = -1; dx <= 1; dx++) {
                ProtoChunk chunk = chunks.get(ChunkPos.pack(cx + dx, cz + dz));
                chunk.setPersistedStatus(ChunkStatus.TERRAIN);
                if (world != null) {
                    world.put(chunk.getPos().pack(), chunk);
                }
            }
        }
        return chunks;
    }

    /** The region for the {@code features} step at {@code cx}, {@code cz}, as its constructor makes it. */
    private static WorldGenRegion region(
            Level level,
            Map<Long, ProtoChunk> chunks,
            NoiseBasedChunkGenerator generator,
            BiomeSource source,
            RandomState state,
            long seed,
            LevelHeightAccessor heights,
            PalettedContainerFactory containers,
            int cx,
            int cz,
            Map<Long, ProtoChunk> starts) throws Exception {
        WorldGenRegion region = (WorldGenRegion) allocate(WorldGenRegion.class);
        ProtoChunk center = chunks.get(ChunkPos.pack(cx, cz));
        StaticCache2D<ChunkAccess> cache = StaticCache2D.create(cx, cz, 8, (x, z) -> {
            if (Math.abs(x - cx) <= 1 && Math.abs(z - cz) <= 1) {
                return chunks.get(ChunkPos.pack(x, z));
            }
            ProtoChunk empty = new ProtoChunk(new ChunkPos(x, z), UpgradeData.EMPTY, heights, containers, null);
            empty.setPersistedStatus(ChunkStatus.STRUCTURE_STARTS);
            if (starts != null) {
                empty.setAllStarts(starts.get(ChunkPos.pack(x, z)).getAllStarts());
            }
            return empty;
        });
        set(region, "cache", cache);
        set(region, "center", center);
        set(region, "level", level);
        set(region, "seed", seed);
        set(region, "levelData", DATA);
        set(region, "random", state.getOrCreateRandomFactory(Identifier.withDefaultNamespace("worldgen_region_random")).at(center.getPos().getWorldPosition()));
        set(region, "dimensionType", level.type);
        set(region, "blockTicks", new net.minecraft.world.ticks.WorldGenTickAccess<Block>(pos -> region.getChunk(pos).getBlockTicks()));
        set(region, "fluidTicks", new net.minecraft.world.ticks.WorldGenTickAccess<Fluid>(pos -> region.getChunk(pos).getFluidTicks()));
        set(region, "generatingStep", ChunkPyramid.GENERATION_PYRAMID.getStepTo(ChunkStatus.FEATURES));
        set(region, "subTickCount", new AtomicLong());
        set(region, "uncachedBiomeResolver", source.createUncachedResolver(state));
        set(region, "centerChunkX", cx);
        set(region, "centerChunkZ", cz);
        set(region, "writeRadius", ChunkPyramid.GENERATION_PYRAMID.getStepTo(ChunkStatus.FEATURES).blockStateWriteRadius());
        set(region, "biomeManager", new BiomeManager(region, BiomeManager.obfuscateSeed(seed)));
        EnvironmentAttributeSystem attributes = EnvironmentAttributeSystem.builder().addStaticLayers(region).build();
        set(region, "environmentAttributes", attributes);
        level.attributes = attributes;
        return region;
    }

    private static final Data DATA = new Data();

    /** The level's data, as far as ticks and mobs ask it: the time is 0 and the difficulty normal. */
    private static final class Data implements LevelData {
        @Override
        public LevelData.RespawnData getRespawnData() {
            return LevelData.RespawnData.DEFAULT;
        }

        @Override
        public long getGameTime() {
            return 0L;
        }

        @Override
        public boolean isHardcore() {
            return false;
        }

        @Override
        public Difficulty getDifficulty() {
            return Difficulty.NORMAL;
        }

        @Override
        public boolean isDifficultyLocked() {
            return false;
        }
    }

    /**
     * A chunk as `terrain`'s fill writes it, then its four final heightmaps, primed if they
     * weren't, its block entities by position, its block and fluid ticks in order, and its
     * entities, each with its UUID zeroed: an entity's UUID comes from a random seeded by the
     * clock, so no two runs give the same.
     */
    private static void write(ProtoChunk chunk, RegistryAccess access, DataOutputStream out, boolean structured) throws IOException {
        TerrainProbe.write(chunk, out);
        for (Heightmap.Types type : FINAL) {
            for (int z = 0; z < 16; z++) {
                for (int x = 0; x < 16; x++) {
                    out.writeInt(chunk.getHeight(type, x, z) + 1);
                }
            }
        }
        Map<BlockPos, CompoundTag> entities = new HashMap<>(chunk.getBlockEntityNbts());
        for (Map.Entry<BlockPos, BlockEntity> e : chunk.getBlockEntities().entrySet()) {
            entities.put(e.getKey(), e.getValue().saveWithFullMetadata(access));
        }
        List<BlockPos> positions = new ArrayList<>(entities.keySet());
        positions.sort(Comparator.comparingInt((BlockPos p) -> p.getY()).thenComparingInt(p -> p.getZ()).thenComparingInt(p -> p.getX()));
        out.writeInt(positions.size());
        for (BlockPos pos : positions) {
            out.writeInt(pos.getX());
            out.writeInt(pos.getY());
            out.writeInt(pos.getZ());
            NbtIo.writeAnyTag(entities.get(pos), out);
        }
        List<SavedTick<Block>> blockTicks = ((ProtoChunkTicks<Block>) chunk.getBlockTicks()).scheduledTicks();
        out.writeInt(blockTicks.size());
        for (SavedTick<Block> t : blockTicks) {
            out.writeInt(BuiltInRegistries.BLOCK.getId(t.type()));
            writeTick(t.pos(), t.priority().getValue(), out);
        }
        List<SavedTick<Fluid>> fluidTicks = ((ProtoChunkTicks<Fluid>) chunk.getFluidTicks()).scheduledTicks();
        out.writeInt(fluidTicks.size());
        for (SavedTick<Fluid> t : fluidTicks) {
            out.writeInt(BuiltInRegistries.FLUID.getId(t.type()));
            writeTick(t.pos(), t.priority().getValue(), out);
        }
        out.writeInt(chunk.getEntities().size());
        for (CompoundTag entity : chunk.getEntities()) {
            CompoundTag masked = entity.copy();
            if (masked.contains("UUID")) {
                masked.putIntArray("UUID", new int[4]);
            }
            if (structured) {
                // Only the type, position and rotation.
                CompoundTag kept = new CompoundTag();
                for (String key : List.of("id", "Pos", "Rotation")) {
                    if (entity.contains(key)) {
                        kept.put(key, entity.get(key).copy());
                    }
                }
                // A shulker keeps the yaw it was made with, drawn from its own random, which is
                // seeded from the clock, since nothing that places one turns it: zeros instead.
                if ("minecraft:shulker".equals(entity.getStringOr("id", "")) && kept.contains("Rotation")) {
                    net.minecraft.nbt.ListTag zero = new net.minecraft.nbt.ListTag();
                    zero.add(net.minecraft.nbt.FloatTag.valueOf(0.0F));
                    zero.add(net.minecraft.nbt.FloatTag.valueOf(0.0F));
                    kept.put("Rotation", zero);
                }
                masked = kept;
            }
            NbtIo.writeAnyTag(masked, out);
        }
    }

    private static void writeTick(BlockPos pos, int priority, DataOutputStream out) throws IOException {
        out.writeInt(pos.getX());
        out.writeInt(pos.getY());
        out.writeInt(pos.getZ());
        out.writeInt(priority);
    }

    private static void set(Object owner, String name, Object value) throws ReflectiveOperationException {
        Field f = WorldGenRegion.class.getDeclaredField(name);
        f.setAccessible(true);
        f.set(owner, value);
    }

    static Object allocate(Class<?> type) throws Exception {
        // `sun.misc.Unsafe`, found by name, since the build takes no warnings.
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field theUnsafe = unsafeClass.getDeclaredField("theUnsafe");
        theUnsafe.setAccessible(true);
        Method allocate = unsafeClass.getMethod("allocateInstance", Class.class);
        return allocate.invoke(theUnsafe.get(null), type);
    }
}
