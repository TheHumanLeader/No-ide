# No-ide

**代码交给 AI，运行留在这里。**

## v0.3：真实 Rust 本地执行器

本地版使用 Rust + Quasar，已经接通真实进程、日志、Git / SVN 状态、Diff、提交和更新。不需要为了控制台安装 Rust、Node.js 或 IDEA；运行自己的项目仍需本机已有对应工具链。

| 已验证运行包 | 验证范围 |
| --- | --- |
| Windows x64 | 39 项真实集成检查通过 |
| Linux x64，Ubuntu 22.04 构建基线 | 39 项集成 + 19 项真实浏览器检查通过 |
| macOS Apple Silicon | 39 项真实集成检查通过 |
| macOS Intel | 编译与 Rust 测试通过，但首个实例启动检查持续超时；本轮不提供未验证包 |

[完整验证记录](prd/verification-v0.3.md) · [已知问题](prd/known-issues-v0.3.md) · [Native executor 工作流](https://github.com/TheHumanLeader/No-ide/actions/workflows/native.yml)

**并非所有目标全绿。** 原生窗口人工操作、外部私有仓库认证、长期性能及完整 Intel Mac 支持均未完成验收。

## 使用本地版

解压完整运行包，保留 `web/` 文件夹。Windows 打开 `Start-No-ide.bat`；Apple Silicon Mac 打开 `No-ide.command`；Linux 运行 `./start.sh`。程序自动打开本地浏览器控制台。

选择项目文件夹 → 确认信任 → 添加运行配置 → 创建一个或多个实例 → 运行。启动器生成本机会话令牌，请勿分享包含令牌的启动地址。

[GitHub Pages 在线页面](https://thehumanleader.github.io/No-ide/) 仍是 v0.2 交互演示。真实运行使用本地包自动打开的地址，不能仅靠打开在线演示访问本机工程。

## Git / SVN 配置

左侧“Git / SVN 配置”：自动检测、本机已安装版本、可执行文件选择、全局配置、项目覆盖、SVN 配置目录。优先级为 **项目指定 > 全局指定 > 自动发现**。

自动发现仅检查 PATH 与常见安装目录，调用实际客户端读取版本；不全盘扫描、不自动安装软件。指定路径失效会报错，不擅自换客户端。沿用本机认证配置，不在项目设置中保存密码或关闭证书验证。

## 运行与代码管理

公共运行命令由配置管理，多个实例独立设置端口、参数、环境变量。支持实际源码监听、构建后重启、构建失败不主动停止旧进程、进程组停止、真实日志和 TCP 就绪检查。

Git：读取状态与 Diff → 暂存 → 检查并本地提交 → 独立确认推送；拉取仅允许快进。

SVN：读取状态与 Diff → 添加选中文件 → 检查并提交到服务器 → 更新工作副本。

提交前显示实际文件与目的地，执行前再次验证。保护未提交修改，不自动丢弃文件、不强制推送。

Linux 上另已实测 Java 21 双实例、源码重编译后真实接口更新、编译失败保留旧响应，以及 Node.js 实际服务更新；不等于 Spring Boot / Android 专项已经完成。

## 当前边界

通用构建后重启不是 JVM 原地 HotSwap。Spring 专用增量构建、Android 完整 ADB 设备部署、clone/checkout、可视化冲突处理、远端执行器和原子构建产物发布尚未实现。Android 当前仅有构建命令模板。

运行包未签名、公证；先使用测试项目。Linux 以 Ubuntu 22.04 x64 构建，不代表所有 Linux 发行版/架构。系统文件选择器提供真实实现，但人工桌面验收仍待完成。

[实现范围](prd/native-v0.3.md)

## 开发

```bash
npm install
npm run check
npm test
npm run build
cargo test --manifest-path backend/Cargo.toml
cargo run --manifest-path backend/Cargo.toml -- --web-dir ./dist
```

Linux 源码构建需要 `libwayland-dev`。发布版前端为静态文件，不需要为控制台常驻 Node.js。

`backend/`：本地 API、客户端检测、进程管理、文件监听、版本管理。

`src/live-*`：真实本机操作台；`src/app.js` 等保留静态演示。

`tests/backend-smoke.py`：39 项真实临时仓库与多实例集成检查。

`tests/native-browser.py`：19 项真实浏览器到执行器的交互检查。

`scripts/package-native.py`：打包二进制、本地页面、依赖锁和构建提交信息。

[原始需求](prd/README.md) · [项目与多实例设计](prd/project-instance-vcs.md) · [协作规则](AGENTS.md)
