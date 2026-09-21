# v0.4.3 Windows 多模块源码一致性修复

日期：2026-09-21。受测与打包源码提交：`579c4fcf29d5a7876ac1d5b2baa1f757d5d35d64`，分支 `feature/easy-run-v0.4`。本文件为交付记录，不改变受测程序。

## 已取回的 Windows 包

- 文件：`No-ide-v0.4.3-windows-x64.zip`
- 字节数：2,335,592
- ZIP SHA-256：`c0e6c796df408a387a8fbcf6e4b73582e1a1830337b5ab4df61090c72b724752`
- EXE SHA-256：`df8f38cbf2e9fcef00b3d89d49e70a125d239164f76275d9a0f762ab139e85a0`
- 工作流：https://github.com/TheHumanLeader/No-ide/actions/runs/35581748156
- 已通过的 Windows 任务：https://github.com/TheHumanLeader/No-ide/actions/runs/35581748156/job/106276074181

Windows Server 2022 x64 任务已完成成功。已下载实际构建包及九份 JSON 报告，逐份确认 passed=true；核对外层和内层 ZIP CRC、PE AMD64 类型、build.json 的版本/提交/运行编号、CRLF 启动脚本、web 入口和资产。交付 ZIP 是 CI 内层原始包，未替换成旧二进制。包内没有字体文件。已查看 Windows 的聚合目录/应用目录配置截图及日志滚动截图。

## 实际修复

旧版自动 Spring Maven 启动只在入口模块执行 compile 和 spring-boot:run：同工程依赖可能仍从本地 Maven 仓库加载以前的同版本 JAR；删除源码和资源后，旧产物也可能残留。入口模块目录直接用作应用工作目录，还可能与 IDE 的根目录启动不同。这些问题不能靠隐藏日志、提高版本号或更改业务 WS 处理器修复。

本版增加：

1. 在受信任项目边界内，有界查找 POM 声明的聚合根。父 POM 不自动等同于聚合 POM。
2. 多模块构建使用聚合 POM、`-pl` 选入口、`--also-make` 让 Maven 选择其依赖；首次启动执行 clean install。之后只在入口模块执行 spring-boot:run，不在所有模块启动应用。
3. 构建与运行沿用相同 Maven、JDK 选择规则、settings.xml、本地仓库及 Maven Profile。install 更新所选本地仓库，不是 Git/SVN 提交，也不是 deploy。
4. 模块目录与应用工作目录分开；多模块默认应用工作目录为聚合根，单模块默认模块目录。都能通过可视化目录选择器调整。工作目录会影响相对的配置、数据和资源位置，不自动移动这些内容。
5. 手动重新构建、停止后的首次启动清理旧产物；普通文件修改增量构建，删除/重命名时触发清理。启用监听的配置会扩展到同工作区声明模块的 src 和 POM，不建立全工程语义索引。
6. 可视化区分 Maven Profile、Spring Profile、应用 JVM 属性和构建属性；保留日志编码选择。添加可选类加载来源诊断，默认关闭，不能把日志滚动窗口当无限诊断归档。
7. 保留日志自动跟随、上翻阅读、回到底部，以及 Git/SVN 批量分组和 .git 本地归组。

高级原始命令配置不自动改写。聚合模块须位于信任边界内；外部模块及复杂动态 Profile 等需要额外验证。

## 本次关键验证：不是只看进程存在

`tests/maven-reactor-043.py` 使用临时合成代码、真实 Maven 3.9.16、Java 8 和 Spring Boot 2.5.15。没有运行或上传用户业务工程、日志、数据库信息或私服配置。

先向隔离的临时本地仓库安装 `common:1.0.0` 的旧 JAR，其中包括一个随后被删除的日志类和资源。修改依赖源码，但保持 artifact 版本不变；删除类和资源，不手动清理旧 target。

以旧单模块配置实际启动后：

- HTTP 返回 `old-installed-jar`；
- 运行时仍能加载已删除的类及资源；
- 真实浏览器 WebSocket 发送测试业务指令，返回 `UNREGISTERED`。

以本版自动聚合启动后：

- HTTP 返回 `current-workspace-source`；
- `Class.forName` 及资源检查确认已删除的类、依赖资源、入口资源均不再存在于实际 classpath；
- 同一个真实 WebSocket 交互返回 `JOINED`；
- 实际 Java 工作目录为聚合根；
- 本地依赖 JAR 的字节摘要确实变化，不是只改界面或日志文字；
- 故意含编译错误的无关模块未被构建；
- 同版本再次改源码并重启、只修改兄弟依赖模块后自动更新、显式覆盖应用工作目录均通过真实进程验证。

这里只证明该缺陷机制和修复在合成项目上成立，不等于已经取得用户业务类的实际加载来源，也不能承诺用户的任意 WS 注册错误必然由同一原因造成。

## Windows 报告

| 报告 | 结果 |
| --- | --- |
| native-Windows-AMD64.json | 39 项真实后端回归通过；health.version 为 0.4.3 |
| native-v04.json | 27 项环境和提交分组回归通过 |
| native-v04-browser.json | 16 项真实界面回归通过 |
| native-metadata.json | 13 项元数据分组回归通过 |
| native-metadata-browser.json | 重复上述 13 项并增加 3 项浏览器检查，共 16 项通过 |
| native-fix-041.json | 43 项批量分组、Maven 与配置回归通过 |
| native-reactor-043.json | 20 项新增多模块、旧类/资源、HTTP 与真实 WS 检查通过 |
| native-log-scroll.json | 24 项真实标准输出、WebSocket 与 DOM 滚动检查通过 |
| native-encoding-042.json | 27 项非 UTF-8 日志及启动回归通过 |

不把重复回归相加宣传成独立功能数。

日志滚动报告的 `backend_version` 字段仍保留了旧脚本的默认字符串 `0.4.2 (reused release)`，该字段是报告元数据错误：state API 不返回版本，脚本错误地使用了回退文字。本次工作流并未复用旧 release，而是同一任务先编译 backend 0.4.3，再运行测试。实际 health 报告、build.json 和二进制摘要均已核对为本次 0.4.3。保留原始 JSON，不事后改写原报告；后续测试应从 health 读取该字段。

## 失败记录和平台边界

首轮 Windows 新夹具的直接 Maven 基线安装因 8.3 临时短路径与规范路径的项目选择不一致而失败；修正为规范路径并显式传入 -f POM 后，本轮包括旧行为复现和修复后的断言全部通过，没有删除旧 JAR/WS/资源断言。

本轮 Linux 的 20 项 Maven 多模块专项也通过，但 Linux 的日志自动滚动测试在显式取消自动滚动的复选框时失败，因此 Linux 任务未成功打包。这一跨平台交互问题仍待排查，不能把 Windows 成功写成整个工作流或全部系统通过。本记录仅交付 Windows 验证范围，不宣称所有 Linux 发行版或 macOS 架构已完整验收。

此前英文 Windows CI（ANSI 1252）上的 Java 8/中文 Maven 安装目录上游启动限制仍被 encoding 报告明确保留；本版不宣称解决该独立问题，不改系统代码页。

## 使用与限制

先停止旧实例并退出旧 No-ide 执行器；同时避免 IDE 的同一业务应用占用相同端口。完整解压新目录，保留 web/，双击 Start-No-ide.bat，确认本机控制台显示 v0.4.3。这次需要新 Rust EXE，仅覆盖旧版 web 不会修复多模块构建。

原有配置目录沿用，升级前建议备份。进入运行配置编辑器，查看“本地源码与依赖模块”：确认入口模块、聚合 POM 和应用工作目录。正常情况下由自动识别完成；不正确时用目录选择器修正。不要为了这次问题清空整个 Maven 仓库或删除数据库；No-ide 不自动调整项目的 JDK、Spring Boot 版本及业务 Profile。

第一次构建会执行所选模块及依赖的 Maven clean/install，通常比单模块 compile 更耗时。Maven 会执行 POM 中声明的生命周期插件。当前使用原项目构建输出，尚非隔离构建或原子发布：No-ide 不提前结束旧进程，不等于 DevTools 或懒加载完全观察不到磁盘产物变化。尤其需要可靠版本回滚的场景不能假定本版已经实现。

运行包未签名，为开发预览；Windows Server 2022 CI 不替代用户 Windows 11、私服、多模块定制和长期负载的实际验收。未自动点击系统文件选择对话框。JVM 原地 HotSwap、Android 完整部署、clone/checkout 及复杂冲突处理不属于本轮完成项。
