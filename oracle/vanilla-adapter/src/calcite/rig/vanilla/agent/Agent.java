package calcite.rig.vanilla.agent;

import java.lang.classfile.ClassFile;
import java.lang.classfile.ClassHierarchyResolver;
import java.lang.classfile.ClassTransform;
import java.lang.classfile.CodeBuilder;
import java.lang.classfile.CodeElement;
import java.lang.classfile.CodeTransform;
import java.lang.classfile.MethodModel;
import java.lang.classfile.MethodTransform;
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
 * <p>Started as {@code -javaagent:agent.jar=seed=N[,tape=PATH][,reseed=T]}. Each
 * {@code ServerLevel}'s constructor, as it returns, calls {@link Levels#made}, which seeds the
 * level's random with {@code mixStafford13(N ^ name.hashCode())}, with the name the dimension's,
 * such as {@code minecraft:overworld}, and sets the entity counter back to 0 as the Overworld's is
 * made. With {@code reseed=T}, {@code ServerLevel.tick} calls {@link Levels#ticking} as it starts,
 * which seeds the level's random so again the first time its tick starts at game time T or later
 * (D316).
 * {@code LegacyRandomSource.next}, which every draw of a level's random comes down to, hands
 * {@link Tape#drew} each value it returns, which writes those of a level's random to the tape.
 * {@code Entity}'s constructor, as it returns, hands the entity to {@link Entities#made}, which
 * seeds its random from the seed and its ID (CAL-148).
 *
 * <p>This class names no game class, so loading it loads none: {@code ServerLevel} and
 * {@code LegacyRandomSource} must load after the transformer is in place to be changed.
 */
public final class Agent {
    private static final String LEVEL = "net/minecraft/server/level/ServerLevel";
    private static final String LEGACY = "net/minecraft/world/level/levelgen/LegacyRandomSource";
    private static final String ENTITY = "net/minecraft/world/entity/Entity";

    private Agent() {
    }

    public static void premain(String arguments, Instrumentation inst) {
        Long seed = null;
        Path tape = null;
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
                default -> throw new IllegalArgumentException("agent: unknown argument " + key);
            }
        }
        if (seed == null) {
            throw new IllegalArgumentException("agent: no seed=N given");
        }
        Tape.start(seed, tape);
        Levels.reseedAt(reseed);
        inst.addTransformer(new Transformer());
    }

    private static final class Transformer implements ClassFileTransformer {
        @Override
        public byte[] transform(ClassLoader loader, String name, Class<?> redefined, ProtectionDomain domain, byte[] bytes) {
            if (!LEVEL.equals(name) && !LEGACY.equals(name) && !ENTITY.equals(name)) {
                return null;
            }
            try {
                ClassLoader from = loader != null ? loader : ClassLoader.getSystemClassLoader();
                ClassFile cf = ClassFile.of(ClassFile.ClassHierarchyResolverOption.of(
                        ClassHierarchyResolver.defaultResolver().orElse(ClassHierarchyResolver.ofResourceParsing(from))));
                return LEVEL.equals(name) ? level(cf, bytes) : ENTITY.equals(name) ? entity(cf, bytes) : legacy(cf, bytes);
            } catch (Throwable t) {
                // A transformer's exception is swallowed by the JVM, and the class loads unchanged,
                // so the run would go on unseeded: stop it instead.
                t.printStackTrace();
                Runtime.getRuntime().halt(70);
                return null;
            }
        }
    }

    // Each of ServerLevel's constructors hands the level to Levels.made before it returns, and its
    // tick hands it to Levels.ticking as it starts.
    private static byte[] level(ClassFile cf, byte[] bytes) {
        MethodTypeDesc withLevel = MethodTypeDesc.of(ConstantDescs.CD_void, ClassDesc.ofInternalName(LEVEL));
        ClassDesc levels = ClassDesc.of("calcite.rig.vanilla.agent.Levels");
        CodeTransform made = (b, e) -> {
            if (e instanceof ReturnInstruction) {
                b.aload(0);
                b.invokestatic(levels, "made", withLevel);
            }
            b.with(e);
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
        ClassTransform both = (cb, ce) -> {
            if (ce instanceof MethodModel m && m.methodName().equalsString("<init>")) {
                cb.transformMethod(m, MethodTransform.transformingCode(made));
            } else if (ce instanceof MethodModel m && m.methodName().equalsString("tick")
                    && m.methodType().equalsString("(Ljava/util/function/BooleanSupplier;)V")) {
                cb.transformMethod(m, MethodTransform.transformingCode(ticking));
            } else {
                cb.with(ce);
            }
        };
        return cf.transformClass(cf.parse(bytes), both);
    }

    // Entity's constructor hands the entity to Entities.made before it returns, once it's given
    // the entity its ID, which its field initializers only mark as unassigned; nothing after
    // draws from its random until a subclass's constructor does.
    private static byte[] entity(ClassFile cf, byte[] bytes) {
        MethodTypeDesc withEntity = MethodTypeDesc.of(ConstantDescs.CD_void, ClassDesc.ofInternalName(ENTITY));
        ClassDesc entities = ClassDesc.of("calcite.rig.vanilla.agent.Entities");
        CodeTransform made = (b, e) -> {
            if (e instanceof ReturnInstruction) {
                b.aload(0);
                b.invokestatic(entities, "made", withEntity);
            }
            b.with(e);
        };
        return cf.transformClass(cf.parse(bytes), ClassTransform.transformingMethodBodies(
                m -> m.methodName().equalsString("<init>"), made));
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
