# No-ide

**代码交给 AI，运行留在这里。**

## v0.3 本地 Rust 执行器

本地版：Rust + Quasar，真实进程、真实日志、真实 Git / SVN 操作。支持构建 Windows x64、Linux x64、macOS Apple Silicon、macOS Intel 四种运行包。平台测试状态以 [Native executor](https://github.com/TheHumanLeader/No-ide/actions/workflows/native.yml) 实际结果为准。

[GitHub Pages](https://thehumanleader.github.io/No-ide/) 仍是 v0.2 的交互演示，不会访问你的本机文件，也不能仅靠打开在线页面启动本机项目。

### 运行本地版

解压完整平台运行包，保留 web/ 文件夹。Windows 打开 Start-No-ide.bat；Mac 打开 No-ide.command；Linux 运行 ./start.sh。程序自动打开本机浏览器控制台，不需要安装 Rust。运行你的项目仍需要本机已有相应 Java / Node / Python 等工具链。

本地默认地址为 http://127.0.0.1:17890；会话令牌由启动器生成，不要把包含令牌的地址分享给别人。

### Git / SVN 配置

左侧“Git / SVN 配置”提供自动检测、已安装版本选择、程序文件选择、全局配置、项目覆盖、SVN 配置目录。优先级为项目指定 > 全局指定 > 自动发现。手动路径失效时报错，不擅自换客户端。不自动安装软件或保存密码，沿用本机凭据配置。

### 项目和实例

选文件夹 → 确认项目受信任 → 添加运行配置 → 创建一个或多个实例。公共命令共用，端口和参数独立。支持真实构建后重启、失败时保留旧进程、子进程停止、实际日志和 TCP 就绪检查。

### 代码管理

Git：真实状态 / Diff → 暂存 → 检查并本地提交 → 独立确认推送；拉取只允许快进。

SVN：真实状态 / Diff → 添加选中文件 → 检查并提交到服务器 → 更新工作副本。

确认会显示实际文件和目的地；工作区变化后需重新确认。不自动丢弃修改，不强制推送。

## 明确边界

这是开发预览，不是完整 IDE 替代品。Java/Spring 专用增量构建与 JVM HotSwap、Android 完整 ADB 设备部署、clone/checkout、冲突解决界面、远端执行器尚未实现。通用命令入口不等于所有框架已逐一验证。

macOS/Windows 包未签名、公证。系统文件选择器还需要真实桌面人工验证。Linux 发布构建以 Ubuntu 22.04 x64 为基线，不代表覆盖所有发行版/架构。

[完整实现说明和限制](prd/native-v0.3.md)

## 开发与验证

```bash
npm install
npm run check
npm test
npm run build
cargo test --manifest-path backend/Cargo.toml
cargo run --manifest-path backend/Cargo.toml -- --web-dir ./dist
```

Linux 构建需要 libwayland-dev；桌面文件选择使用系统对话框。生产版本前端是静态文件，无需为控制台常驻 Node.js。

- `backend/`：本地 API、客户端检测、进程管理、文件监听、SCM 操作。
- `src/live-*`：真实本地操作台；`src/app.js` 等保留旧的模拟预览。
- `tests/backend-smoke.py`：临时本地仓库和多实例真实集成验证。
- `tests/native-browser.py`：真实浏览器到本地执行器的点击验证。
- `scripts/package-native.py`：跨平台打包。
- [原产品需求](prd/README.md) / [项目多实例与版本管理](prd/project-instance-vcs.md) / [协作规则](AGENTS.md)。

未经测试的目标不写成已完成能力。测试报告由工作流输出，与对应提交和运行平台绑定。
