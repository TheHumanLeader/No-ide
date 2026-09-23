# GitHub Releases：公开下载与发布

## 下载

- 所有发行版：https://github.com/TheHumanLeader/No-ide/releases
- 当前 v0.5.1：https://github.com/TheHumanLeader/No-ide/releases/tag/v0.5.1
- 历史 v0.5.0：https://github.com/TheHumanLeader/No-ide/releases/tag/v0.5.0

2026-09-23 已公开发布 v0.5.1，非草稿，仍为 Pre-release。附件为 Windows x64、macOS Apple Silicon 的原始编译包，另有 SHA256SUMS.txt 与 release-manifest.json。下载 Assets 中的 No-ide-v…zip；Source code 是源码。

Windows 通过完整平台任务及新反馈浏览器检查。Mac ARM64 通过原生/编码范围，未执行浏览器、构建反馈和 HotSwap 专项。Linux 本轮增量脚本在实例仍启动中时提前请求 run.repair，被状态校验拒绝，任务未全通过；Intel Mac 基础进程回归失败。这两个平台没有上传运行包。

[本版完整验证记录](verification-v0.5.1.md)。未把不同版本或失败平台产物混入同一发行版。

## 本次出处

- 标签 v0.5.1 指向受测源码 `c7735dfd8f85d4b54485930fc53a0c90417053f4`。
- 原生编译流程：https://github.com/TheHumanLeader/No-ide/actions/runs/35840836367
- 发布流程：https://github.com/TheHumanLeader/No-ide/actions/runs/35841467909
- Release ID：394491136。
- Windows ZIP SHA-256：700721b9b2c283b080a717cf29c6455b475708bb12064194abc2d6f8b20b08f7。

运行包是平台 CI 的原始 ZIP，不由发布脚本重新编译。包内 build.json 与发行标签指向同一个源码提交。main 只更新发布工具和文档，程序源码以相应标签/开发分支为准。

## 以后发布

先运行 Native executor 构建测试，再在 Actions → Publish Release → Run workflow 输入 run_id 和准确版本号，或修改 releases/publish.json 后提交。版本必须与包内 version 一致。

发布流程最多等待原生构建结束 20 分钟，并要求 Windows 平台任务成功；其余平台由 allow_partial 决定：true 只发布通过的平台，false 缺任意平台即停止。默认保持开发预览，不自动提升为稳定版。

发布器检查原始 artifact 摘要、ZIP CRC、CPU 架构、web/agent/启动器、build.json 的版本/源码/流程编号，再校验远端上传摘要。原有标签指向不一致时拒绝，不移动标签，不覆盖其他版本的附件。

可以在 releases/v<版本>.md 编写本版功能说明。scripts/append_release_notes.py 仅在原发布器完成验证后加入这些说明，不替换二进制、标签或可见性；重复运行使用新生成的基础说明，不重复追加。

该流程不允许从 fork 或 pull_request 构建发布；只读取本仓库受信任 push/workflow_dispatch 的原生流程。部分平台失败不会被描述成全部平台通过。未签名/公证状态与每个平台未测范围应保持在版本说明中。
