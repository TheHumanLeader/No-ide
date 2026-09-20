# v0.3 真实执行器验证记录

日期：2026-09-20。受测执行器与前端源码提交：`afb1575b0266b017cb9eba5cd9cda3a3c53ab4f8`。

工作流：https://github.com/TheHumanLeader/No-ide/actions/runs/35501028750

## 发布范围与实际结果

| 目标 | 实际结果 | 本轮运行包 |
| --- | --- | --- |
| Windows x64，windows-2022 CI | Rust 测试、release 构建、39 项真实 API / 进程 / Git / SVN 集成检查通过 | 提供 |
| Linux x64，Ubuntu 22.04 CI | Rust 测试、release 构建、39 项集成检查、19 项真实浏览器交互检查通过 | 提供 |
| macOS Apple Silicon，macos-14 CI | Rust 测试、release 构建、39 项真实集成检查通过 | 提供 |
| macOS Intel，macos-15-intel CI | Rust 测试与 release 构建通过；集成检查在首个 Python 服务等待运行时超时；重试仍复现 | 暂不提供未验证包 |

**整个四目标工作流不是全绿。** 不能把三个成功目标写成全部平台/架构都已验证，也不能把 Intel Mac 编译通过说成运行通过。Intel Mac 在健康检查、认证保护、Git/SVN 检测和配置等 11 项通过后，于首个实例启动等待超时；目前还不能确定故障原因。完整支持 Intel Mac 是待修事项。

## 39 项真实集成检查

使用一次性临时项目与本地 Git bare / SVN file:// 仓库，不触碰用户业务代码、外部远程仓库和认证凭据。

覆盖：本机服务启动、HTTP 认证、Origin/Host 限制、Git/SVN 实际版本检测、无效手动路径拒绝、全局配置持久化、项目覆盖、目录越界拒绝、重复端口拒绝、双实例与子进程、实际端口/环境变量、共享构建、源码监听更新、构建失败保留旧 PID 和响应、子进程组停止、停止不影响另一实例、取消正在运行的构建、真实日志、Git 状态和 Diff、确认失效和防重放、实际暂存集合、保留未选择文件、本地提交不自动推送、显式推送、保护未提交修改、仅快进拉取、SVN 状态和 Diff、仅提交选中文件、SVN 服务器内容变化、更新保护，以及最终配置保存。

脚本：`tests/backend-smoke.py`。

## 19 项真实浏览器检查

Linux CI 中运行 Chromium，直接打开 Rust 服务提供的 Vite / Quasar 生产构建，不用模拟接口，不以 HTML 截图代替点击测试。

覆盖：真实适配器与空状态、实际客户端版本、项目加载、运行配置保存、实例保存、运行按钮启动真实进程并展示 PID、HTTP 结果、停止按钮、真实 Git Diff、统一/并排切换、暂存确认、实际 Git index 变化、提交去向确认、真实本地 commit、刷新后配置保留、390px 窄屏和无未捕获浏览器错误。

项目目录的测试注册通过本机 API 完成，**没有自动点击系统文件选择器**。不能把这组测试写成三平台 GUI 原生对话框均已验证。

脚本：`tests/native-browser.py`。工作流产物包含报告与 `native-tools.png`、`native-running.png`、`native-diff.png`、`native-mobile.png`。

## Linux 补充 Java / Node 实测

将上述已构建 Linux 运行包取回工作容器，实际使用 OpenJDK 21.0.11、Node.js 22.16.0 完成 7 项额外检查：

1. Java 源码由 javac 编译，实际启动 HTTP 服务。
2. 同一配置启动两个 Java 进程，端口独立。
3. 修改 Java 源码后自动重新编译、重启，两路实际 HTTP 响应从 java-v1 变为 java-v2。
4. 故意引入 Java 语法错误，旧 PID 和 java-v2 响应保留。
5. Node.js 实际 HTTP 服务启动。
6. 修改 Node 源码后自动重启，实际响应由 node-v1 变为 node-v2。
7. 所有 Java / Node 实例停止。

这验证的是通用构建后重启，不是 JVM 原地 HotSwap，也不是 Spring Boot / Android 专项测试。记录随本次交付的验证包提供。

## 资源占用短测

同一个 Linux release 二进制在工作容器启动，空项目、完成一次客户端检测、不打开浏览器、没有项目进程或监听任务：VmRSS 为 4176 KiB，约 4.1 MiB；二进制 3,139,424 字节。观察窗口 5 秒。

这是单次短测，不是长期性能基准，也不包括浏览器、Git/SVN 临时进程、构建工具或运行中的应用，更不是 Windows/macOS 的占用承诺。不得据此宣称所有使用情形只占 4 MB 或永远不卡顿。

## 仍未验证或未实现

完整 Intel Mac 运行；Windows 11 / 用户自己的桌面环境人工验收；三平台原生文件选择器人工点击；外部私有 Git/SVN 服务器认证；长期压力测试；专用 Java/Spring 增量构建和 JVM HotSwap；Android ADB 完整部署；clone/checkout；复杂冲突与目录提交；原子构建产物发布。

二进制未签名、公证。先在测试项目上验证；没有声称经过商店认证。详细实现范围见 `native-v0.3.md`。
