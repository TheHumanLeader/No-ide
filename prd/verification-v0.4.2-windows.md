# v0.4.2 Windows 编码修复包验证

日期：2026-09-21。运行包对应源码：`423c0cfe695784895c9d5b213fdd3da579d87341`，分支 `feature/easy-run-v0.4`。本文件为交付记录，不改变受测程序。

## 运行包

文件：`No-ide-v0.4.2-windows-x64.zip`，2,292,304 字节。

SHA-256：`fcc22015cdffb2c9575b555e1ab8120dde818a5582a6e1c4a6fab43a7d6cfd72`。

工作流：https://github.com/TheHumanLeader/No-ide/actions/runs/35561002389

Windows 任务：https://github.com/TheHumanLeader/No-ide/actions/runs/35561002389/job/106213793451

Windows Server 2022 x64 任务成功完成：Rust 测试与 release 构建、既有真实回归、浏览器检查、批量分组与 Maven 专项、新增编码专项、打包和上传。

已下载实际运行包和七份 JSON 报告，逐一确认 passed=true。已核对外层/内层 ZIP CRC、Windows AMD64 PE 机器类型、build.json 的版本/源码提交/运行编号、CRLF 启动脚本及完整 web 资产。交付 ZIP 为 CI 生成的原始内层包，未混用旧版程序；包内不含字体文件。

## 修复的实际问题

v0.4.1 将构建日志与路径、仓库状态等机器输出共用严格 UTF-8 解析，构建程序即使退出码为 0，也可能因日志为 GBK 等编码而阻止应用启动。

v0.4.2 把人类可读日志与机器数据分开。构建和运行日志使用有界、分流的增量解码；构建成败保留真实退出码，不因显示解码错误变成构建失败。路径、Git/SVN 状态等机器数据继续严格校验，不将替换字符用作执行路径。

运行配置支持自动、UTF-8、GBK/CP936、GB18030、系统编码。自动模式是日志显示启发式，不是对任意混合编码的准确保证；显式选择可用于特殊程序。此设置只改变 No-ide 的日志显示，不修改源码编码、系统区域设置、JAVA_HOME 或 JVM file.encoding。旧配置默认自动。

此前的 Maven/Gradle 选择、运行配置编辑、整行勾选、批量分组和 SVN .git 归组功能保留。

## 实际报告

| 报告 | 结果 |
| --- | --- |
| native-Windows-AMD64.json | 39 项既有真实后端回归通过 |
| native-v04.json | 27 项环境和分组检查通过 |
| native-v04-browser.json | 16 项真实界面检查通过 |
| native-metadata.json | 13 项元数据分组检查通过 |
| native-metadata-browser.json | 13 项重复回归和 3 项浏览器检查通过，共 16 项 |
| native-fix-041.json | 43 项批量操作、Maven 与配置检查通过 |
| native-encoding-042.json | 27 项新增编码、实际构建启动和界面检查通过 |

不把重复测试计为额外独立能力。

新增编码检查包括：中文含空格目录中的真实进程、GBK 构建输出、逐字节写入的 stdout/stderr、旧配置默认自动后成功启动、真实退出码 7 与错误正文、失败保留旧 PID/HTTP 响应、执行器重启后编码设置保留、源码字节未改变、Git 中文文件名与目录越界保护。

Maven 专项使用真实 Maven 3.9.16、Java 8 1.8.0_504 和 Spring Boot 2.7.18。原始 Maven 输出通过字节检查，确实不是 UTF-8，且包含 GBK 中文标记；不是只测一段模拟日志。自动显示模式下构建后应用成功启动，实际 HTTP 响应确认 Java 版本、参数属性与工作目录。随后通过真实 Quasar 页面选择 GBK、保存并运行，验证真实构建日志、Spring stdout/stderr 中文文本和无未捕获页面异常。已查看 Windows 运行截图。

测试为产生确定的旧编码日志，仅对一次性测试 JVM 设置 MAVEN_OPTS 的 file.encoding/标准流编码；产品代码不会自动加这些参数。此前仅设置标准流编码时，Maven 日志已经在生产者侧变成 ASCII 问号，原始字节断言正确拒绝了该测试样本；现在真实 GBK 字节断言仍保留并通过。

## 必须单独保留的上游限制

本次英文 Windows CI 的 ANSI 代码页为 1252。Java 8 不经过 No-ide，直接运行中文安装目录中的原始 mvn.cmd --version，也会返回退出码 1：找不到 org.codehaus.plexus.classworlds.launcher.Launcher。默认 JVM 参数、file.encoding=GBK、仅标准流编码 GBK 三组基线均失败。

这是独立的上游路径兼容问题，没有被日志解码修复。报告明确记录 upstream_java8_unicode_maven_supported=false、maven_fixture_uses_chinese_paths=false 和 known_limitations。实际 Maven/Spring GBK 专项因此使用含空格的 ASCII 临时安装/项目/配置/仓库目录；中文路径在原生 Python/Rust 进程专项中验证，不能混称为 Java 8 中文安装路径已经通过。

没有为通过测试更改系统代码页、静默改用其他 JDK或重写用户工程路径。原始基线失败与后续实际 GBK 输出均保留在报告，不能把这一发布说成解决所有 Java 8 跨区域路径问题。

## 使用和升级

停止旧实例并关闭旧执行器，将完整新包解压到新文件夹，保留 web/，双击 Start-No-ide.bat。浏览器自动打开本机控制台，界面版本应为 v0.4.2。系统用户配置目录仍沿用；升级前建议备份，避免新旧执行器同时写入。

可先沿用原项目、Maven 与 Java 配置运行。日志默认自动；需要明确 GBK 显示时：运行台 → 运行配置 → 编辑配置 → 展开 JVM 参数、系统属性与启动配置 → 日志编码 → GBK/CP936 → 保存。不要为了日志显示设置去修改系统区域或源码编码。

## 验证边界

运行包未签名，是开发预览。上述 Windows Server 2022 CI 检查不等于用户 Windows 11/PMS 工程、企业私服认证、全部多模块组合或长期负载已经验收。没有自动点击原生系统文件选择对话框。GitHub Pages 仍是演示，真实执行需本地运行包。

本记录只确认上述 Windows 范围，不将单目标通过写成所有 Linux 发行版和 Mac 架构均已完成。JVM 原地 HotSwap、Android 全套部署、clone/checkout 和复杂冲突处理仍不在本次修复范围。
