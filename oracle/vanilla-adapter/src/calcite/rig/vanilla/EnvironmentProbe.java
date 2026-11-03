package calcite.rig.vanilla;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.JsonOps;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.Holder;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.attribute.AttributeTypes;
import net.minecraft.world.attribute.EnvironmentAttribute;
import net.minecraft.world.attribute.EnvironmentAttributeMap;
import net.minecraft.world.attribute.EnvironmentAttributeSystem;
import net.minecraft.world.attribute.WeatherAttributes;
import net.minecraft.world.clock.ClockInstance;
import net.minecraft.world.clock.ClockManager;
import net.minecraft.world.clock.WorldClock;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.timeline.Timeline;

/**
 * `environment`: vanilla's own {@link EnvironmentAttributeSystem}, built as a level builds its
 * own but for the biomes, and each attribute the case reads, at each record's clocks and weather,
 * as {@code getDimensionValue} gives it.
 *
 * <p>The layers are a dimension type's: its attributes, then each of its timelines in order, then
 * the weather's, if the case says the level can have weather, as {@code addDefaultLayers} adds
 * them. The type is vanilla's, by {@code type}, or made of {@code attributes_map}, an attribute
 * map as a dimension type's {@code attributes} are written, and {@code timelines}, timelines as
 * their files are written. Every clock is at the record's ticks, and the weather access gives the
 * record's rain and thunder levels.
 */
final class EnvironmentProbe implements Probe {
    @Override
    public String name() {
        return "environment";
    }

    @Override
    public int version() {
        return 1;
    }

    @Override
    public Result run(JsonObject input, List<byte[]> blobs) {
        RegistryAccess.Frozen access = RegistriesProbe.access();
        RegistryOps<JsonElement> ops = access.createSerializationContext(JsonOps.INSTANCE);
        EnvironmentAttributeMap attributes = EnvironmentAttributeMap.EMPTY;
        List<Holder<Timeline>> timelines = new ArrayList<>();
        if (input.has("type")) {
            if (input.has("attributes_map") || input.has("timelines")) {
                throw new CaseError("`type` is given without `attributes_map` or `timelines`");
            }
            Identifier id = identifier(Args.string(input, "type"), "`type`");
            DimensionType type = access.lookupOrThrow(Registries.DIMENSION_TYPE)
                    .get(ResourceKey.create(Registries.DIMENSION_TYPE, id))
                    .orElseThrow(() -> new CaseError("no dimension type `" + id + "`"))
                    .value();
            attributes = type.attributes();
            type.timelines().forEach(timelines::add);
        } else {
            if (input.has("attributes_map")) {
                attributes = decode(EnvironmentAttributeMap.CODEC.parse(ops, input.get("attributes_map")), "`attributes_map`");
            }
            if (input.has("timelines")) {
                JsonArray list = Args.array(input, "timelines");
                for (int i = 0; i < list.size(); i++) {
                    timelines.add(Holder.direct(decode(Timeline.DIRECT_CODEC.parse(ops, list.get(i)), "`timelines`[" + i + "]")));
                }
            }
        }
        JsonElement weatherField = Args.field(input, "weather");
        if (!weatherField.isJsonPrimitive() || !weatherField.getAsJsonPrimitive().isBoolean()) {
            throw new CaseError("`weather` must be a boolean");
        }
        JsonArray names = Args.array(input, "read");
        List<EnvironmentAttribute<?>> read = new ArrayList<>();
        for (int i = 0; i < names.size(); i++) {
            Identifier id = identifier(Args.asString(names.get(i), "`read`[" + i + "]"), "`read`[" + i + "]");
            EnvironmentAttribute<?> attribute = BuiltInRegistries.ENVIRONMENT_ATTRIBUTE.getOptional(id)
                    .orElseThrow(() -> new CaseError("no environment attribute `" + id + "`"));
            if (attribute.type() != AttributeTypes.FLOAT && attribute.type() != AttributeTypes.BOOLEAN) {
                throw new CaseError("`" + id + "` is neither a float nor a boolean");
            }
            read.add(attribute);
        }
        Clocks clocks = new Clocks();
        Weather weather = new Weather();
        EnvironmentAttributeSystem.Builder builder = EnvironmentAttributeSystem.builder().addConstantLayer(attributes);
        for (Holder<Timeline> t : timelines) {
            builder.addTimelineLayer(t, clocks);
        }
        if (weatherField.getAsBoolean()) {
            WeatherAttributes.addBuiltinLayers(builder, weather);
        }
        EnvironmentAttributeSystem system = builder.build();
        ByteBuffer records = Args.records(blobs, 16);
        int width = 0;
        for (EnvironmentAttribute<?> a : read) {
            width += a.type() == AttributeTypes.FLOAT ? 4 : 1;
        }
        ByteBuffer out = ByteBuffer.allocate(records.capacity() / 16 * width);
        while (records.hasRemaining()) {
            clocks.ticks = records.getLong();
            weather.rain = records.getFloat();
            weather.thunder = records.getFloat();
            // A new tick, as `ServerLevel.tick` starts one.
            system.invalidateTickCache();
            for (EnvironmentAttribute<?> a : read) {
                Object value = system.getDimensionValue(a);
                if (a.type() == AttributeTypes.FLOAT) {
                    // Every NaN as one, as no code sees a NaN's sign or payload (D198).
                    out.putInt(Float.floatToIntBits((Float) value));
                } else {
                    out.put((byte) ((Boolean) value ? 1 : 0));
                }
            }
        }
        return Result.ok(new JsonObject(), out.array());
    }

    private static Identifier identifier(String text, String what) {
        Identifier id = Identifier.tryParse(text);
        if (id == null) {
            throw new CaseError(what + " must be an identifier");
        }
        return id;
    }

    private static <T> T decode(DataResult<T> result, String what) {
        return result.resultOrPartial().filter(v -> result.error().isEmpty())
                .orElseThrow(() -> new CaseError(what + " doesn't read: " + result.error().map(e -> e.message()).orElse("")));
    }

    /** Every clock at the record's ticks. */
    private static final class Clocks implements ClockManager, ClockInstance {
        long ticks;

        @Override
        public ClockInstance getInstance(Holder<WorldClock> clock) {
            return this;
        }

        @Override
        public long totalTicks() {
            return this.ticks;
        }

        @Override
        public float partialTick() {
            return 0.0F;
        }

        @Override
        public float rate() {
            return 1.0F;
        }

        @Override
        public boolean isPaused() {
            return false;
        }
    }

    /** The record's rain and thunder levels, as {@code getRainLevel(1.0F)} and {@code getThunderLevel(1.0F)} would give them. */
    private static final class Weather implements WeatherAttributes.WeatherAccess {
        float rain;
        float thunder;

        @Override
        public float rainLevel() {
            return this.rain;
        }

        @Override
        public float thunderLevel() {
            return this.thunder;
        }
    }
}
