package noide.agent;

import java.io.*;
import java.lang.instrument.*;
import java.lang.management.ManagementFactory;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/** No-ide local development agent. No remote bind, HTTP, path RPC or eval.
 * The only mutation is a bounded, authenticated batch of approved class bodies.
 * This agent is installed at startup, never attached to an unrelated process.
 */
public final class Agent {
    static final int MAX_CLASS = 4 * 1024 * 1024, MAX_TOTAL = 32 * 1024 * 1024, MAX_COUNT = 512;
    static Instrumentation instrumentation;
    static final List<Path> roots = new ArrayList<>();
    static final Map<String, String> loadedHashes = new ConcurrentHashMap<>();
    static volatile boolean foreignRedefinition = false;
    static final ThreadLocal<Boolean> updating = new ThreadLocal<>();
    static String token;
    public static void premain(String path, Instrumentation inst) throws Exception {
        instrumentation = inst;
        if (!inst.isRedefineClassesSupported()) throw new IOException("JVM does not support class redefinition");
        Properties p = new Properties();
        try (Reader r = Files.newBufferedReader(Paths.get(path), StandardCharsets.UTF_8)) { p.load(r); }
        token = p.getProperty("token", "");
        if (token.length() < 32 || token.length() > 64) throw new IOException("invalid agent token");
        int count = Integer.parseInt(p.getProperty("roots", "0"));
        if (count < 1 || count > 256) throw new IOException("invalid output roots");
        for (int i = 0; i < count; i++) roots.add(Paths.get(p.getProperty("root." + i)).toRealPath());
        inst.addTransformer(new ClassFileTransformer() {
            public byte[] transform(ClassLoader loader, String name, Class<?> redef, ProtectionDomain domain, byte[] bytes) {
                try {
                    int root = source(domain);
                    if (root < 0 || loader != ClassLoader.getSystemClassLoader()) return null;
                    if (redef != null) { if (!Boolean.TRUE.equals(updating.get())) foreignRedefinition = true; }
                    else if (loadedHashes.size() < 200000) loadedHashes.put(root + ":" + name.replace('/', '.'), hash(bytes));
                } catch (Exception ignored) { }
                return null;
            }
        });
        final ServerSocket server = new ServerSocket();
        server.bind(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0), 4);
        Thread worker = new Thread(() -> serve(server), "no-ide-hotswap"); worker.setDaemon(true); worker.start();
        Path endpoint = Paths.get(p.getProperty("endpoint"));
        Path tmp = endpoint.resolveSibling("endpoint.tmp");
        String pid = ManagementFactory.getRuntimeMXBean().getName().split("@")[0];
        Files.write(tmp, (server.getLocalPort() + "\n" + pid + "\n").getBytes(StandardCharsets.US_ASCII));
        Files.move(tmp, endpoint, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        System.err.println("[No-ide] HotSwap agent ready; local authenticated control; DevTools restart disabled for this process.");
    }
    static int source(ProtectionDomain d) throws Exception {
        if (d == null || d.getCodeSource() == null) return -1;
        URL u = d.getCodeSource().getLocation(); if (!u.getProtocol().equals("file")) return -1;
        Path p = Paths.get(u.toURI()).toRealPath();
        return roots.indexOf(p);
    }
    static String hash(byte[] bytes) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes); char[] result = new char[64]; char[] hex = "0123456789abcdef".toCharArray();
        for (int i=0; i<digest.length; i++) {int v=digest[i]&255; result[2*i]=hex[v>>>4]; result[2*i+1]=hex[v&15];} return new String(result);
    }
    static String string(DataInputStream in, int max) throws IOException {
        int length = in.readInt(); if (length < 0 || length > max) throw new IOException("invalid frame length");
        byte[] b = new byte[length]; in.readFully(b);
        return new String(b, StandardCharsets.UTF_8);
    }
    static void string(DataOutputStream out, String s) throws IOException {
        byte[] b = s.getBytes(StandardCharsets.UTF_8); out.writeInt(b.length); out.write(b);
    }
    static final class Patch { int root; String name; Path path; byte[] old, next; Class<?> type; }
    static void serve(ServerSocket server) {
        while (!server.isClosed()) {
            try (Socket socket = server.accept()) {
                socket.setSoTimeout(5000);
                DataInputStream in = new DataInputStream(socket.getInputStream());
                DataOutputStream out = new DataOutputStream(socket.getOutputStream());
                try {
                    if (!string(in, 16).equals("NOIDE-HS1")) throw new IOException("invalid protocol");
                    if (!MessageDigest.isEqual(string(in, 64).getBytes(StandardCharsets.US_ASCII), token.getBytes(StandardCharsets.US_ASCII))) throw new IOException("unauthorized");
                    String op = string(in, 16);
                    if (!op.equals("check") && !op.equals("apply")) throw new IOException("invalid operation");
                    if (foreignRedefinition) throw new IllegalArgumentException("Another agent changed application classes; restart required");
                    int count = in.readInt(); if (count < 0 || count > MAX_COUNT) throw new IOException("too many classes");
                    List<Patch> patches = new ArrayList<>(); Set<String> seen = new HashSet<>(); int total = 0;
                    Map<String, Class<?>> loaded = new HashMap<>();
                    for (Class<?> c : instrumentation.getAllLoadedClasses()) {
                        try {
                            int root = source(c.getProtectionDomain()); if (root < 0) continue;
                            String key = root + ":" + c.getName();
                            if (c.getClassLoader() != ClassLoader.getSystemClassLoader() || loaded.containsKey(key)) loaded.put(key, null); else loaded.put(key, c);
                        } catch (Exception ignored) { }
                    }
                    for (int i = 0; i < count; i++) {
                        Patch a = new Patch(); a.root = in.readInt();
                        if (a.root < 0 || a.root >= roots.size()) throw new IOException("invalid root");
                        String rel = string(in, 4096), expected = string(in, 64);
                        if (!rel.endsWith(".class") || rel.contains("\\") || rel.startsWith("/") || rel.contains(":") || Arrays.asList(rel.split("/")).contains("..")) throw new IOException("invalid class path");
                        int size = in.readInt(); total += size;
                        if (size < 1 || size > MAX_CLASS || total > MAX_TOTAL) throw new IOException("patch too large");
                        a.next = new byte[size]; in.readFully(a.next);
                        a.path = roots.get(a.root).resolve(rel).toRealPath();
                        if (!a.path.startsWith(roots.get(a.root)) || Files.size(a.path) > MAX_CLASS) throw new IOException("outside snapshot");
                        a.old = Files.readAllBytes(a.path); a.name = Shape.name(a.next);
                        String key = a.root + ":" + a.name;
                        if (!seen.add(key) || !a.name.equals(Shape.name(a.old)) || !a.name.replace('.', '/').concat(".class").equals(rel)) throw new IOException("class name mismatch");
                        if (!expected.equals(hash(a.old)) || !expected.equals(loadedHashes.get(key))) throw new IllegalArgumentException("Class not loaded from verified snapshot: " + a.name);
                        a.type = loaded.get(key);
                        if (a.type == null || !instrumentation.isModifiableClass(a.type)) throw new IllegalArgumentException("Class not loaded / custom loader / not modifiable: " + a.name);
                        if (!Arrays.equals(Shape.policy(a.old), Shape.policy(a.next))) throw new IllegalArgumentException("Schema, annotation, constant, constructor or initialization changed: " + a.name);
                        patches.add(a);
                    }
                    if (op.equals("apply") && !patches.isEmpty()) apply(patches);
                    string(out, "ok"); string(out, "verified " + patches.size() + " loaded classes; " + op);
                } catch (Throwable e) {
                    string(out, "restart"); string(out, e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()));
                }
                out.flush();
            } catch (IOException ignored) { }
        }
    }
    static void apply(List<Patch> patches) throws Exception {
        List<Path> prepared = new ArrayList<>();
        try {
            for (Patch p : patches) { Path t = Files.createTempFile(p.path.getParent(), ".noide-", ".class.tmp"); prepared.add(t); Files.write(t, p.next); }
            ClassDefinition[] definitions = new ClassDefinition[patches.size()];
            for (int i = 0; i < definitions.length; i++) definitions[i] = new ClassDefinition(patches.get(i).type, patches.get(i).next);
            updating.set(true);
            try { instrumentation.redefineClasses(definitions); } finally { updating.remove(); }
            for (int i = 0; i < patches.size(); i++) {
                Patch p = patches.get(i);
                loadedHashes.put(p.root + ":" + p.name, hash(p.next));
                try { Files.move(prepared.get(i), p.path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
                catch (IOException e) { foreignRedefinition = true; throw new IOException("JVM changed but snapshot persistence failed; restart required", e); }
            }
        } finally { for (Path p : prepared) Files.deleteIfExists(p); }
    }
}
