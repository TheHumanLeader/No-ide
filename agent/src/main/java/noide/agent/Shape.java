package noide.agent;

import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** A deliberately conservative, constant-pool-independent HotSwap policy.
 * Keep constructors, class initializers, field values, annotations and schema.
 * Erase ordinary method bodies only. Unknown custom attributes are unsupported.
 */
final class Shape {
    static ClassNode read(byte[] bytes) {
        ClassNode n = new ClassNode();
        new ClassReader(bytes).accept(n, ClassReader.SKIP_DEBUG | ClassReader.SKIP_FRAMES);
        return n;
    }
    static byte[] policy(byte[] bytes) {
        ClassNode n = read(bytes);
        if (n.attrs != null && !n.attrs.isEmpty()) throw new IllegalArgumentException("unknown class attributes");
        Collections.sort(n.fields, Comparator.comparing(f -> f.name + f.desc));
        Collections.sort(n.methods, Comparator.comparing(m -> m.name + m.desc));
        for (FieldNode f : n.fields) {
            if (f.attrs != null && !f.attrs.isEmpty()) throw new IllegalArgumentException("unknown field attributes");
        }
        for (MethodNode m : n.methods) {
            if (m.attrs != null && !m.attrs.isEmpty()) throw new IllegalArgumentException("unknown method attributes");
            if (!m.name.startsWith("<") && !initializationMethod(m)) {
                m.instructions.clear(); m.tryCatchBlocks.clear(); m.localVariables = null;
                m.visibleLocalVariableAnnotations = null; m.invisibleLocalVariableAnnotations = null;
                m.maxStack = 0; m.maxLocals = 0;
            }
        }
        ClassWriter w = new ClassWriter(0); n.accept(w); return w.toByteArray();
    }
    private static boolean initializationMethod(MethodNode m) {
        List<AnnotationNode> a = new ArrayList<>();
        if (m.visibleAnnotations != null) a.addAll(m.visibleAnnotations);
        if (m.invisibleAnnotations != null) a.addAll(m.invisibleAnnotations);
        for (AnnotationNode n : a) {
            if (n.desc.equals("Lorg/springframework/context/annotation/Bean;")
                || n.desc.endsWith("/PostConstruct;") || n.desc.endsWith("/PreDestroy;")) return true;
        }
        return m.name.equals("afterPropertiesSet") && m.desc.equals("()V");
    }
    static String name(byte[] bytes) { return new ClassReader(bytes).getClassName().replace('/', '.'); }
}
