# GitHub Releases：公开下载与发布

## 下载

- 所有发行版：https://github.com/TheHumanLeader/No-ide/releases
- v0.5.0 开发预览：https://github.com/TheHumanLeader/No-ide/releases/tag/v0.5.0

2026-09-23 已公开发布，非草稿。当前附件为 Windows x64、macOS Apple Silicon 两个平台的 v0.5.0 原始编译运行包，另有 SHA256SUMS.txt 与 release-manifest.json。下载 Assets 中的 No-ide-v…zip；GitHub 自动提供的 Source code 只是源码。

当前平台情况：

| 平台 | 状态 |
| --- | --- |
| Windows x64 | 平台编译、原生及浏览器回归、HotSwap 专项通过；在 Windows Server 2022 验证，不代替全部桌面环境验收 |
| macOS ARM64 | 平台原生及编码回归通过；浏览器和 HotSwap 专项未在 Mac 执行 |
| Linux x64 | 日志跟随回归仍失败，不上传该平台包 |
| macOS Intel x64 | 基础进程集成回归失败，不上传该平台包 |

所有包未签名/公证，作为开发预览发布，不标为生产稳定版。没有用旧版本包填补缺失平台。

## 本次出处

- 发行源码/标签：07c08d85686feaf131d4af96231249df963ac306 / v0.5.0。
- 原生编译工作流：https://github.com/TheHumanLeader/No-ide/actions/runs/35693646509
- 发布工作流：https://github.com/TheHumanLeader/No-ide/actions/runs/35823775244
- Release ID：394326765。
- Windows ZIP SHA-256：79186ae8a25a5dd154c529664741dfcf4117d5621389bef2ddc54ea51ef700d7。
- macOS ARM64 ZIP SHA-256：e78ab5871d2eb44eb785485ddec8180b2bdca45e22fc80b5473604975107c07b。

发行包并非此次发布脚本重新编译，保留原平台 CI 生成的 ZIP。包内 build.json 与标签指向同一源码提交。只新增发布机制和文档，没有把开发分支的程序代码合并到 main。

## 以后如何发布

1. 先运行现有 Native executor 编译/测试流程，等待结束。记录这个流程的 run ID（地址中 actions/runs/ 后的数字）。
2. 在 Actions → Publish Release → Run workflow 中选择 main，输入 run_id 与准确版本号（例如 0.5.1，必须与包内版本一致）。
3. 发布器检查平台任务、原始 artifact 摘要、ZIP CRC、CPU 架构、web/agent/启动器、build.json 的版本/提交/流程编号，然后将原始运行包发布到 Releases。

也可修改 main 上 releases/publish.json 后提交，触发相同发布流程。该文件的 allow_partial=true 明确允许只发布通过的平台；改为 false 时，缺任意平台都会停止发布。默认始终为 Pre-release，不自动提升到稳定版。

为新版本发布前应核对 scripts/publish_release.py 中的版本功能说明和当前验证边界，使说明与该版本匹配。发布流程只负责使用 Native executor 产物，不替代原生编译或测试。

## 发布安全规则

- 不允许从 fork 或 pull_request 工作流发布，仅读取本仓库受信任 push/workflow_dispatch 的原生流程。
- 部分平台失败时逐个平台检查；不把整体失败的流程误说成全平台通过，也不丢掉其他平台已通过的原始包。
- 创建标签时固定到实际受测源码提交；现有标签指向不同时直接拒绝，不移动标签。
- 先创建草稿，上传全部附件并核对服务器摘要，再公开发布。
- 重试不覆盖已上传内容，不移动既有标签；已公开资产不同即报错，不强制覆盖。
- 只发布平台运行 ZIP、校验文件和来源清单，不上传用户源码、配置、数据库或业务日志。
- 发布权限仅在受信任发布任务中授予 contents:write / actions:read；不向 fork 授权、不读取额外凭据。
- scripts/test_publish_release.py 的 14 项测试检查有效平台、错版本/提交/流程、缺文件、错误架构、路径穿越、私有配置和字体混入等拒绝路径。
