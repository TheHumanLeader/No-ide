# v0.4.0 Windows 交付验证

日期：2026-09-21。运行包对应源码提交：`ddee33fcf8ad663eaaf27ebf6dab865e774b12c7`，分支 `feature/easy-run-v0.4`。本文件仅补充测试记录，不改变受测程序。

## 可运行包

`No-ide-v0.4.0-windows-x64.zip`，2,093,875 字节，包含 Windows AMD64 原生 `no-ide.exe`、CRLF 启动脚本 `Start-No-ide.bat`、完整 Quasar 生产构建 `web/`、依赖锁、许可证说明和 `build.json`。

SHA-256：`4ed46cae5dd38595f4d9c9a87e012d347d62f4eff038c3b7767a90b7e14dae3f`。

构建记录：https://github.com/TheHumanLeader/No-ide/actions/runs/35548954836

Windows 任务：https://github.com/TheHumanLeader/No-ide/actions/runs/35548954836/job/106180043981

任务实际完成：Rust 测试、release 编译、真实后端回归、新环境与分组集成检查、真实 Chromium 界面检查、打包与产物上传，均成功。

## 实际测试结果

Windows Server 2022 x64 的独立 runner 上：

- 39 项既有真实 API / 多实例 / 文件监听 / Git / SVN 回归检查通过。
- 27 项运行环境与持久化变更分组检查通过。
- 16 项真实 Quasar 页面到 Rust 后端的 Chromium 检查通过，无未捕获页面错误。

已经下载并核对该运行的 `native-Windows-AMD64.json`、`native-v04.json` 和 `native-v04-browser.json`，三者 passed 均为 true；已查看 Windows 运行配置截图。取回的 ZIP 通过 CRC 检查；核对了 PE AMD64 机器类型、build.json 的版本与源码提交、启动脚本和新界面资产。

## 与本轮用户需求直接相关的验证

Java 8 与 Java 17 实际同时登记并分别用于实例运行；Java 系统属性、环境变量和包含空格的程序参数确实进入进程。Node.js / Python 自动生成的命令实际执行；实例引用的环境不是仅修改界面显示。

选择项目后静态发现入口；网页运行入口和环境可下拉选择，目录字段由选择器提供，可视化行编辑器配置入参和环境变量。浏览器按钮启动真实 HTTP 服务，实际接口响应验证参数与变量内容。

Git 默认组提交没有包含另一组已经暂存的 keep.txt，且该文件仍保持暂存。SVN 默认组提交只更改被确认文件，另一组服务器内容保持不变。文件提交变为干净后、实际重启执行器后，再次修改仍保留自定义分组。分组变化使旧确认失效，删除分组回到默认且不删除源文件。

浏览器验证新建分组、批量移动、拖动移动、查看 Diff、默认组提交确认、实际 Git 提交，以及刷新后归属保留。390px 运行环境和分组页面无横向页面溢出。

## 使用与升级

先停止旧实例并关闭旧执行器，再把新包完整解压到新文件夹，双击 `Start-No-ide.bat`。保留 web 目录，不需要安装 Rust 或为了控制台安装 Node.js / IDEA；运行用户项目仍需本机相应工具链。系统用户配置目录中的既有配置继续使用，升级前建议备份，避免旧版继续写入新版配置。

本地版才会真实操作项目，GitHub Pages 仍是演示。运行环境、自动入口、可视化参数与 Git/SVN 分组界面都已包含在该 Windows 包中。

## 验证边界

这是 Windows Server 2022 CI 验证，不代替用户 Windows 11 桌面人工验收。原生 OS 文件选择对话框没有被自动点击，私有远端认证、长期负载和复杂项目兼容未全部测试。运行包未签名，先在测试工程使用。分组提交按文件当前完整内容，不是逐块暂存提交；不会修改 .gitignore / svn:ignore。

本记录不宣布所有 Linux 发行版或 Mac 架构都通过。本版仍不是完整 IDEA：JVM 原地 HotSwap、Android 完整部署、clone/checkout 和复杂冲突处理仍是后续事项。
