# Windows Java 8 中文 Maven 安装目录基线

2026-09-21。在 Windows Server 2022、系统 ANSI 代码页 1252 的 CI 机器上，复制真实 Maven 到中文安装目录，使用选定 Java 8 直接调用上游 mvn.cmd --version，未经过 No-ide。

三个对照（默认 JVM 参数、file.encoding=GBK、仅 stdout/stderr 编码 GBK）均返回退出码 1：Could not find or load main class org.codehaus.plexus.classworlds.launcher.Launcher。

原始报告：工作流 35559907108 的 native-report-windows-x64 / native-encoding-042.json。这个上游路径兼容问题与 No-ide 把非 UTF-8 构建日志误判为失败是不同问题，不能声称日志修复解决了它。

编码回归现在区分两组：
1. 原生进程在中文含空格路径下构建、运行并逐字节输出 GBK，验证 No-ide 解码与路径安全。
2. 真实 Java 8 + Maven + Spring Boot 产生非 UTF-8 构建输出，验证退出码、启动、接口响应和界面日志编码。当上游中文安装目录基线不能启动时，测试使用含空格的 ASCII 临时安装/项目目录，报告明确写入 known_limitations 和 maven_fixture_uses_chinese_paths=false，不计为 Java 8 中文路径通过。

这一调整只涉及临时测试工程，不修改产品的路径选择、不切换用户 JDK、不改区域设置，也不跳过真实 Maven 构建或非 UTF-8 字节断言。用户工程应继续使用原配置；本修复包不承诺修复 Java 8 本身的跨系统代码页路径兼容问题。
