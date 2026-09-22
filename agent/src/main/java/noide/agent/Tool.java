package noide.agent;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import java.nio.charset.StandardCharsets;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

/** Build a short, Unicode-safe manifest classpath and resolve the compiled main.
 * No user code is loaded or executed here. All paths come from the Rust planner.
 */
public final class Tool {
    public static void main(String[] args) throws Exception {
        if (args.length != 5 || !args[0].equals("classpath")) throw new IllegalArgumentException("invalid tool arguments");
        Path output = Paths.get(args[1]);
        String preferred = args[4];
        List<String> mains = new ArrayList<>(), spring = new ArrayList<>();
        try (java.util.stream.Stream<Path> files = Files.walk(output)) {
            Iterator<Path> it = files.iterator(); int count = 0;
            while (it.hasNext()) {
                Path p = it.next();
                if (++count > 200000) throw new IOException("too many class files");
                if (!p.toString().endsWith(".class") || !Files.isRegularFile(p)) continue;
                if (Files.size(p) > 4 * 1024 * 1024) throw new IOException("class file too large");
                ClassNode n = Shape.read(Files.readAllBytes(p));
                boolean main = false;
                for (MethodNode m : n.methods) if (m.name.equals("main") && m.desc.equals("([Ljava/lang/String;)V") && (m.access & 9) == 9) main = true;
                if (main) {
                    String name = n.name.replace('/', '.'); mains.add(name);
                    if (n.visibleAnnotations != null) for (AnnotationNode a : n.visibleAnnotations)
                        if (a.desc.equals("Lorg/springframework/boot/autoconfigure/SpringBootApplication;")) spring.add(name);
                }
            }
        }
        if (preferred.isEmpty() || preferred.equals("pom.xml") || preferred.contains("${")) {
            List<String> candidates = spring.isEmpty() ? mains : spring;
            if (candidates.size() != 1) throw new IOException("Cannot uniquely select compiled main class: " + candidates + "; set main class in No-ide");
            preferred = candidates.get(0);
        } else if (!mains.contains(preferred)) throw new IOException("Configured main class not found: " + preferred);
        StringBuilder cp = new StringBuilder();
        for (String line : Files.readAllLines(Paths.get(args[2]), StandardCharsets.UTF_8)) {
            if (line.isEmpty()) continue;
            Path p = Paths.get(line).toRealPath();
            cp.append(p.toUri().toASCIIString()).append(' ');
        }
        Manifest mf = new Manifest(); mf.getMainAttributes().putValue("Manifest-Version", "1.0");
        mf.getMainAttributes().putValue("Class-Path", cp.toString().trim());
        try (JarOutputStream jar = new JarOutputStream(Files.newOutputStream(Paths.get(args[3])), mf)) { }
        System.out.write((preferred + "\n").getBytes(StandardCharsets.UTF_8));
    }
}
