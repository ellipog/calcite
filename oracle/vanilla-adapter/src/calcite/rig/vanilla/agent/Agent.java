package calcite.rig.vanilla.agent;

import java.lang.classfile.ClassFile;
import java.lang.classfile.ClassHierarchyResolver;
import java.lang.classfile.ClassTransform;
import java.lang.classfile.CodeBuilder;
import java.lang.classfile.CodeElement;
import java.lang.classfile.CodeTransform;
import java.lang.classfile.MethodModel;
import java.lang.classfile.MethodTransform;
import java.lang.classfile.Opcode;
import java.lang.classfile.instruction.InvokeInstruction;
import java.lang.classfile.instruction.ReturnInstruction;
import java.lang.constant.ClassDesc;
import java.lang.constant.ConstantDescs;
import java.lang.constant.MethodTypeDesc;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.nio.file.Path;
import java.security.ProtectionDomain;

/**
 * The rig's Java agent (P6.1, D311): it makes a vanilla server's levels draw the same from run to
 * run, and from what Calcite draws with the same seed, and can write every draw a level's random
 * makes to a tape.
 *
 * <p>Started as {@code -javaagent:agent.jar=seed=N[,tape=PATH][,reseed=T][,trace=PATH]}. Each
 * {@code ServerLevel}'s constructor, once {@code Level}'s returns, calls {@link Levels#made},
 * which seeds the level's random with {@code mixStafford13(N ^ name.hashCode())}, with the name
 * the dimension's, such as {@code minecraft:overworld}, and sets the entity counter back to 0 as
 * the Overworld's is made, before anything else draws from it (D623). With {@code reseed=T},
 * {@code ServerLevel.tick} calls {@link Levels#ticking} as it starts, which seeds the level's
 * random so again the first time its tick starts at game time T or later (D316).
 * {@code LegacyRandomSource.next}, which every draw of a level's random comes down to, hands
 * {@link Tape#drew} each value it returns, which writes those of a level's random to the tape.
 * {@code Entity}'s constructor, once it's given the entity its ID and before it calls
 * {@code defineSynchedData}, hands the entity to {@link Entities#made}, which seeds its random from
 * the seed and its ID (CAL-148). With {@code trace=PATH},
 * {@code ServerLevel.tickNonPassenger} hands each entity it's ticked to {@link Trace#ticked} as it
 * returns, which writes a living one's state, and {@code ServerPlayer.doTick} hands the player to
 * {@link Trace#played} as it returns (CAL-159). {@code Brain.Provider.makeBrain} hands the entity
 * it's making a brain for to {@link Entities#braining} as it starts and calls
 * {@link Entities#brained} as it returns, and each of {@code ShufflingList}'s constructors hands
 * its random to {@link Entities#shuffling} as it returns, which seeds it (CAL-160).
 * {@code InsideBrownianWalk}'s {@code Collections.shuffle}, which draws from a random of its own
 * vanilla seeds from the clock, is {@link Entities#shuffle} instead, with the mob it walks.
 *
 * <p>This class names no game class, so loading it loads none: {@code ServerLevel} and
 * {@code LegacyRandomSource} must load after the transformer is in place to be changed.
 */
public final class Agent {
    private static final String LEVEL = "net/minecraft/server/level/ServerLevel";
    private static final String BASE = "net/minecraft/world/level/Level";
    private static final String LEGACY = "net/minecraft/world/level/levelgen/LegacyRandomSource";
    private static final String ENTITY = "net/minecraft/world/entity/Entity";
    private static final String PLAYER = "net/minecraft/server/level/ServerPlayer";
    private static final String PROVIDER = "net/minecraft/world/entity/ai/Brain$Provider";
    private static final String SHUFFLING = "net/minecraft/world/entity/ai/behavior/ShufflingList";
    private static final String INSIDE = "net/minecraft/world/entity/ai/behavior/InsideBrownianWalk";

    private Agent() {
    }

    public static void premain(String arguments, Instrumentation inst) {
        Long seed = null;
        Path tape = null;
        Path trace = null;
        long reseed = -1;
        for (String part : (arguments == null ? "" : arguments).split(",")) {
            if (part.isEmpty()) {
                continue;
            }
            int eq = part.indexOf('=');
            String key = eq < 0 ? part : part.substring(0, eq);
            String value = eq < 0 ? "" : part.substring(eq + 1);
            switch (key) {
                case "seed" -> seed = Long.parseLong(value);
                case "tape" -> tape = Path.of(value);
                case "reseed" -> reseed = Long.parseLong(value);
                case "trace" -> trace = Path.of(value);
                default -> throw new IllegalArgumentException("agent: unknown argument " + key);
            }
        }
        if (seed == null) {
            throw new IllegalArgumentException("agent: no seed=N given");
        }
        Tape.start(seed, tape);
        Trace.start(trace);
        Levels.reseedAt(reseed);
        inst.addTransformer(new Transformer());
    }

    private static final class Transformer implements ClassFileTransformer {
        @Override
        public byte[] transform(ClassLoader loader, String name, Class<?> redefined, ProtectionDomain domain, byte[] bytes) {
            if (!LEVEL.equals(name) && !LEGACY.equals(name) && !ENTITY.equals(name) && !PLAYER.equals(name)
                    && !PROVIDER.equals(name) && !SHUFFLING.equals(name) && !INSIDE.equals(name)) {
                return null;
            }
            try {
                ClassLoader from = loader != null ? loader : ClassLoader.getSystemClassLoader();
                ClassFile cf = ClassFile.of(ClassFile.ClassHierarchyResolverOption.of(
                        ClassHierarchyResolver.defaultResolver().orElse(ClassHierarchyResolver.ofResourceParsing(from))));
                return LEVEL.equals(name) ? level(cf, bytes) : ENTITY.equals(name) ? entity(cf, bytes)
                        : PLAYER.equals(name) ? player(cf, bytes) : PROVIDER.equals(name) ? provider(cf, bytes)
                        : SHUFFLING.equals(name) ? shuffling(cf, bytes) : INSIDE.equals(name) ? inside(cf, bytes)
                        : legacy(cf, bytes);
            } catch (Throwable t) {
                // A transformer's exception is swallowed by the JVM, and the class loads unchanged,
                // so the run would go on unseeded: stop it instead.
                t.printStackTrace();
                Runtime.getRuntime().halt(70);
                return null;
            }
        }
    }

    // ServerLevel's constructor hands the level to Levels.made once Level's constructor, which
    // makes its random, returns, and before the rest of it: the End's dragon fight draws its boss
    // bar's UUID from the level's random as it's made, as Calcite's does from the seeded one
    // (D623). Its tick hands it to Levels.ticking as it starts, and tickNonPassenger hands it and
    // the entity to Trace.ticked as it returns.
    private static byte[] level(ClassFile cf, byte[] bytes) {
        MethodTypeDesc withLevel = MethodTypeDesc.of(ConstantDescs.CD_void, ClassDesc.ofInternalName(LEVEL));
        ClassDesc levels = ClassDesc.of("calcite.rig.vanilla.agent.Levels");
        int[] hooked = {0};
        CodeTransform made = (b, e) -> {
            b.with(e);
            if (e instanceof InvokeInstruction i && i.opcode() == Opcode.INVOKESPECIAL && i.name().equalsString("<init>")
                    && i.owner().asInternalName().equals(BASE)) {
                b.aload(0);
                b.invokestatic(levels, "made", withLevel);
                hooked[0]++;
            }
        };
        CodeTransform ticking = new CodeTransform() {
            @Override
            public void atStart(CodeBuilder b) {
                b.aload(0);
                b.invokestatic(levels, "ticking", withLevel);
            }

            @Override
            public void accept(CodeBuilder b, CodeElement e) {
                b.with(e);
            }
        };
        MethodTypeDesc withTwo = MethodTypeDesc.of(ConstantDescs.CD_void, ConstantDescs.CD_Object, ConstantDescs.CD_Object);
        CodeTransform ticked = (b, e) -> {
            if (e instanceof ReturnInstruction) {
                b.aload(0);
                b.aload(1);
                b.invokestatic(ClassDesc.of("calcite.rig.vanilla.agent.Trace"), "ticked", withTwo);
            }
            b.with(e);
        };
        ClassTransform both = (cb, ce) -> {
            if (ce instanceof MethodModel m && m.methodName().equalsString("<init>")) {
                cb.transformMethod(m, MethodTransform.transformingCode(made));
            } else if (ce instanceof MethodModel m && m.methodName().equalsString("tickNonPassenger")) {
                cb.transformMethod(m, MethodTransform.transformingCode(ticked));
            } else if (ce instanceof MethodModel m && m.methodName().equalsString("tick")
                    && m.methodType().equalsString("(Ljava/util/function/BooleanSupplier;)V")) {
                cb.transformMethod(m, MethodTransform.transformingCode(ticking));
            } else {
                cb.with(ce);
            }
        };
        byte[] out = cf.transformClass(cf.parse(bytes), both);
        if (hooked[0] != 1) {
            throw new IllegalStateException("ServerLevel's constructors call Level's " + hooked[0] + " times, not once");
        }
        return out;
    }

    // Entity's constructor hands the entity to Entities.made once it's given the entity its ID,
    // which its field initializers only mark as unassigned, and before it calls
    // defineSynchedData: a zombie villager's draws its profession from the entity's random, as
    // Calcite's does from the seeded one (CAL-194). Nothing else draws from it until a subclass's
    // constructor does. The call's arguments are on the stack already, which the seeding leaves.
    private static byte[] entity(ClassFile cf, byte[] bytes) {
        MethodTypeDesc withEntity = MethodTypeDesc.of(ConstantDescs.CD_void, ClassDesc.ofInternalName(ENTITY));
        ClassDesc entities = ClassDesc.of("calcite.rig.vanilla.agent.Entities");
        int[] hooked = {0};
        CodeTransform made = (b, e) -> {
            if (e instanceof InvokeInstruction i && i.name().equalsString("defineSynchedData")) {
                b.aload(0);
                b.invokestatic(entities, "made", withEntity);
                hooked[0]++;
            }
            b.with(e);
        };
        byte[] out = cf.transformClass(cf.parse(bytes), ClassTransform.transformingMethodBodies(
                m -> m.methodName().equalsString("<init>"), made));
        if (hooked[0] != 1) {
            throw new IllegalStateException("Entity's constructors call defineSynchedData " + hooked[0] + " times, not once");
        }
        return out;
    }

    // ServerPlayer.doTick hands the player to Trace.played as it returns.
    private static byte[] player(ClassFile cf, byte[] bytes) {
        MethodTypeDesc withOne = MethodTypeDesc.of(ConstantDescs.CD_void, ConstantDescs.CD_Object);
        CodeTransform played = (b, e) -> {
            if (e instanceof ReturnInstruction) {
                b.aload(0);
                b.invokestatic(ClassDesc.of("calcite.rig.vanilla.agent.Trace"), "played", withOne);
            }
            b.with(e);
        };
        return cf.transformClass(cf.parse(bytes), ClassTransform.transformingMethodBodies(
                m -> m.methodName().equalsString("doTick") && m.methodType().equalsString("()V"), played));
    }

    // Brain.Provider.makeBrain hands its body to Entities.braining as it starts, and calls
    // Entities.brained before it returns, the brain it returns left on the stack (CAL-160).
    private static byte[] provider(ClassFile cf, byte[] bytes) {
        ClassDesc entities = ClassDesc.of("calcite.rig.vanilla.agent.Entities");
        MethodTypeDesc withOne = MethodTypeDesc.of(ConstantDescs.CD_void, ConstantDescs.CD_Object);
        MethodTypeDesc withNone = MethodTypeDesc.of(ConstantDescs.CD_void);
        int[] hooked = {0};
        CodeTransform braining = new CodeTransform() {
            @Override
            public void atStart(CodeBuilder b) {
                b.aload(1);
                b.invokestatic(entities, "braining", withOne);
                hooked[0]++;
            }

            @Override
            public void accept(CodeBuilder b, CodeElement e) {
                if (e instanceof ReturnInstruction) {
                    b.invokestatic(entities, "brained", withNone);
                }
                b.with(e);
            }
        };
        byte[] out = cf.transformClass(cf.parse(bytes), ClassTransform.transformingMethodBodies(
                m -> m.methodName().equalsString("makeBrain"), braining));
        if (hooked[0] != 1) {
            throw new IllegalStateException("Brain.Provider has " + hooked[0] + " makeBrain methods, not one");
        }
        return out;
    }

    // Each of ShufflingList's constructors hands its random to Entities.shuffling as it returns
    // (CAL-160).
    private static byte[] shuffling(ClassFile cf, byte[] bytes) {
        ClassDesc list = ClassDesc.ofInternalName(SHUFFLING);
        ClassDesc source = ClassDesc.of("net.minecraft.util.RandomSource");
        MethodTypeDesc withOne = MethodTypeDesc.of(ConstantDescs.CD_void, ConstantDescs.CD_Object);
        CodeTransform made = (b, e) -> {
            if (e instanceof ReturnInstruction) {
                b.aload(0);
                b.getfield(list, "random", source);
                b.invokestatic(ClassDesc.of("calcite.rig.vanilla.agent.Entities"), "shuffling", withOne);
            }
            b.with(e);
        };
        return cf.transformClass(cf.parse(bytes), ClassTransform.transformingMethodBodies(
                m -> m.methodName().equalsString("<init>"), made));
    }

    // InsideBrownianWalk's Collections.shuffle(List) is Entities.shuffle(List, Object) instead,
    // with the mob the lambda that calls it is given, the first of its parameters that's a
    // PathfinderMob, loaded from its slot (CAL-160).
    private static byte[] inside(ClassFile cf, byte[] bytes) {
        ClassDesc collections = ClassDesc.of("java.util.Collections");
        ClassDesc mob = ClassDesc.of("net.minecraft.world.entity.PathfinderMob");
        MethodTypeDesc withTwo = MethodTypeDesc.of(ConstantDescs.CD_void, ClassDesc.of("java.util.List"), ConstantDescs.CD_Object);
        int[] hooked = {0};
        ClassTransform each = (cb, ce) -> {
            if (!(ce instanceof MethodModel m)) {
                cb.with(ce);
                return;
            }
            MethodTypeDesc type = m.methodTypeSymbol();
            int slot = (m.flags().flagsMask() & ClassFile.ACC_STATIC) != 0 ? 0 : 1;
            int body = -1;
            for (ClassDesc p : type.parameterList()) {
                if (p.equals(mob)) {
                    body = slot;
                    break;
                }
                slot += p.equals(ConstantDescs.CD_long) || p.equals(ConstantDescs.CD_double) ? 2 : 1;
            }
            int at = body;
            CodeTransform swap = (b, e) -> {
                if (at >= 0 && e instanceof InvokeInstruction i && i.owner().asSymbol().equals(collections)
                        && i.name().equalsString("shuffle") && i.typeSymbol().parameterCount() == 1) {
                    b.aload(at);
                    b.invokestatic(ClassDesc.of("calcite.rig.vanilla.agent.Entities"), "shuffle", withTwo);
                    hooked[0]++;
                    return;
                }
                b.with(e);
            };
            cb.transformMethod(m, MethodTransform.transformingCode(swap));
        };
        byte[] out = cf.transformClass(cf.parse(bytes), each);
        if (hooked[0] != 1) {
            throw new IllegalStateException("InsideBrownianWalk calls Collections.shuffle " + hooked[0] + " times, not once");
        }
        return out;
    }

    // LegacyRandomSource.next(int) hands each value it returns, itself and the bits to Tape.drew.
    private static byte[] legacy(ClassFile cf, byte[] bytes) {
        MethodTypeDesc drew = MethodTypeDesc.of(ConstantDescs.CD_void, ConstantDescs.CD_int, ConstantDescs.CD_Object, ConstantDescs.CD_int);
        CodeTransform hook = (b, e) -> {
            if (e instanceof ReturnInstruction) {
                b.dup();
                b.aload(0);
                b.iload(1);
                b.invokestatic(ClassDesc.of("calcite.rig.vanilla.agent.Tape"), "drew", drew);
            }
            b.with(e);
        };
        return cf.transformClass(cf.parse(bytes), ClassTransform.transformingMethodBodies(
                m -> m.methodName().equalsString("next") && m.methodType().equalsString("(I)I"), hook));
    }
}
