# v0.5 原地热替换与增量构建

实现目标：日常操作分为应用改动、重启实例、清理重建。测试结果以版本验证记录为准，本文件不预先宣布通过。

## 用户操作

在 Spring Boot / Maven 自动运行配置中选择“优先原地热替换”。原配置不静默切换。停止后启动一次加载内置 Agent，之后应用改动先执行模块级增量构建，再校验并热替换。兼容模式仍是增量构建后重启，不冒充热替换。

应用改动：无变化跳过；支持的已加载方法体原地替换，PID 不变。结构、初始化、注解、资源、新增/删除文件、未加载类或第三方依赖变化，显示待重启，不自动结束应用。重启实例：检查最新输出，只重启指定实例，不强制全量清理。清理重建：独立确认的修复入口。

## 实现

沿用 0.4.4 内容指纹模型，修改模块及下游消费者重编，未变上游复用；不是单个 .java 精细增量。有效 POM、Profile、环境、JDK、Maven、已解析依赖或输出变化使缓存失效，未知自定义输入保守处理。

Maven 提供运行依赖清单，本地模块普通 JAR 替换为经验证的本次编译输出。启动实际 Java 进程，使用私有输出和依赖副本，防止后续 clean/build 改坏运行中的 classpath。短 manifest classpath JAR 使用文件 URI，避免长命令和中文路径拼接。模块目录与应用工作目录继续分开。

内置 Java 8 Agent 在启动时安装，ASM 命名空间隔离。只绑定 loopback，使用实例随机令牌和有界二进制协议；不提供 HTTP、任意路径读取、脚本执行或远端附加。每批最多 512 个类、32 MiB，单类 4 MiB；私有类路径最多 200000 文件项和 4 GiB。

替换前校验实际加载类来源、旧文件摘要、当前 classloader 和可修改能力。字节码比较保留结构、注解、常量、构造器、静态初始化、Bean 和常见初始化方法，只允许普通方法体变化。调用 Instrumentation.redefineClasses，不靠重新创建 JVM 伪装。初始化时本进程禁用 DevTools restart，避免重复处理。其他 Agent、调试器和复杂类加载器不在首轮支持范围。

## 边界

已有对象状态不重新计算，正在执行的旧调用可以继续旧字节码，任意一次性业务逻辑不会自动重新执行。新增/删除方法或字段需要确认重启；框架资源刷新未实现。单 JVM 的 redefine 批次有 JVM 的失败语义，但文件持久化异常须标为未确认；多 JVM 更新不是跨进程事务，不能承诺失败时全部回滚。业务外部配置和数据库不属于 classpath 私有副本。

本轮仅为 Spring Boot / Maven 自动入口提供该路径，其他语言保留原行为。首轮构建和复制仍有成本，不承诺任意工程秒级。SDK 和 Maven 配置不自动升级。

## 验证

tests/hotswap-050.py：真实 Maven / Java 8 与 Java 17 / Spring Boot，多模块修改，同一个 HTTP 应用的 PID、Bean 初始化标记、计数状态和同一个 WebSocket 连接在修改方法后保留且返回新值；结构/注解/资源/删除/初始化变化等待重启；编译失败不污染旧私有副本；无变化不构建；上游稳定 JAR 字节和时间戳不动；兄弟模块 watcher；鉴权失败不改变代码；保留原分组、编码、滚动回归。

参考：
- https://docs.oracle.com/javase/8/docs/api/java/lang/instrument/Instrumentation.html
- https://docs.spring.io/spring-boot/docs/2.5.15/reference/html/using.html#using.devtools.restart
- https://maven.apache.org/plugins/maven-dependency-plugin/build-classpath-mojo.html
