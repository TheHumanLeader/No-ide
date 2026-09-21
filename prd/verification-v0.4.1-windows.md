# v0.4.1 Windows 修复包与验证记录

日期：2026-09-21。受测源码提交：`f225e5d4c659ed1e0ed12ed828d4739e2efaa188`，分支 `feature/easy-run-v0.4`。本文件是交付记录，不改变受测程序。

## 可运行包

`No-ide-v0.4.1-windows-x64.zip`，2,140,771 字节。

SHA-256：`3f8a1ac21620aff086161b307e506f3a6c631dd8b3f55d698e074eb9843cb057`。

构建：https://github.com/TheHumanLeader/No-ide/actions/runs/35556404711

Windows 任务：https://github.com/TheHumanLeader/No-ide/actions/runs/35556404711/job/106200840054

Windows Server 2022 x64 任务已完成成功：Rust 测试、release 构建、后端回归、环境和分组检查、真实浏览器检查、150 文件与 Maven 专项、打包和上传。已取回运行包、报告和截图，核对 ZIP CRC、Windows AMD64 PE 类型、启动脚本、web 文件、版本、源码提交与运行编号。包内不含字体文件。

## 本轮修复

### SVN 中的 .git 可以移分组

分组不再调用用于 Diff/提交的元数据路径保护；只记本机的仓库相对路径标签。允许 `.git` 目录、`.git` 指针文件和其他工具元数据目录移入“忽略不提交”等任意自定义分组。目录标签可向子路径继承，明确指定的子路径可覆盖。

实际访问内容和版本控制写操作仍保护 `.git` / `.svn`；点击这类行正常勾选，右侧显示说明，不调用读取内部内容的 Diff。移动分组不修改磁盘中的原目录，也不改 `.gitignore` / `svn:ignore`。绝对路径和 `..` 越界仍拒绝。

真实 SVN 测试验证：默认组提交只改变 work.txt，服务器没有 .git，原 .git/config 的字节校验不变。实际重启后归属保持；SVN 客户端被故意设为不可用时，分组仍能保存。

### 批量选择和移动

点整行切换 checkbox 和行高亮。支持 Shift 范围选择、全选、反选、清空、文件/目录名筛选后全选、Ctrl/Command+A。底部固定提供“已选 X 项、目标分组、移动选中文件”。拖动只是可选方式。

一次移动最多 2000 个路径，一次 API 写入，不调用 Git/SVN，不拉取完整 state/status，不刷新整个工作台。Diff 独立防抖和有界排队，不阻塞勾选。保存后才确认成功，保存失败不伪装已经写入。

Windows CI 单次 150 文件样本：Git 与 SVN 的浏览器点击至列表更新均约 63 ms；客户端故意不可用时，本机分组 API 分别约 32 ms、15 ms。此为独立 runner 上的小样本实测，不是用户 PMS 工程的测量，也不是全部机器/负载的延迟保证。

### 提交命名

SVN 按钮明确为“纳入版本控制（不提交）”；Git 暂存明确标注“不提交”，放入独立操作区。真正提交使用“检查并提交选中 X 项”或明确列出组名的整组提交，仍须确认文件与去向。Git 分组提交使用当前完整文件内容，非逐块提交，其他组已暂存文件也不会夹带。

### Maven 和运行配置

运行环境页新增 Maven/Gradle 构建工具区，支持本机发现、安装目录选择、Maven settings.xml 和本地仓库路径选择。构建工具与 JDK 分开；运行配置可覆盖构建工具。可定位已有 IDEA 安装中的 Maven，不需要打开 IDEA。

运行台直接显示已有配置，提供编辑、复制、添加实例；实例中的配置名称可直接进入对应编辑器。编辑保留配置 ID 与实例引用，不再误建副本。检查启动条件显示实际 Maven 程序；路径失效给出具体原因，不再只抛 program not found。

后台 Maven/Gradle 版本检测使用独立状态，不锁住其他页面保存按钮。

## 实际测试

报告已逐一读取并确认 passed=true：

| 脚本 / 报告 | Windows 结果 |
| --- | --- |
| backend-smoke.py / native-Windows-AMD64.json | 39 项既有真实回归通过 |
| workbench-v04.py / native-v04.json | 27 项环境、分组与提交隔离检查通过 |
| browser-v04.py / native-v04-browser.json | 16 项真实界面检查通过 |
| metadata_groups.py / native-metadata.json | 13 项真实 SVN 元数据分组检查通过 |
| metadata_groups.py --browser / native-metadata-browser.json | 重复上述 13 项，再加 3 项真实浏览器检查通过 |
| fix-041.py / native-fix-041.json | 43 项 150 文件批量操作、Maven 与运行配置专项通过 |

Maven 专项不是模拟脚本：使用真实 Maven 3.9.16、Java 8（1.8.0_504）和 Spring Boot 2.7.18，实际编译并启动 HTTP 服务，验证带空格的入参、JVM 属性和环境变量。安装目录、settings.xml 和本地仓库路径包含空格。通过界面编辑属性后重新启动，实际 HTTP 响应变为编辑后的值。Maven 选择在真实执行器重启后仍保留。

测试中修正了 Windows 临时路径的 8.3 短名与规范长名比较方式：使用 samefile 验证实际文件身份，不弱化为仅检查字符串包含 Maven；原始检测结果记录在 JSON。Mac 的停止等待测试改为等待真实 stopped 状态，而不是假设停止请求立即完成。

测试只使用一次性临时工程与本地 Git bare / SVN file:// 测试仓库，不接触用户 PMS 业务代码和私有远程仓库。已查看 Windows 的批量分组、.git 归组和运行配置编辑截图。

## 升级与使用

先停止旧实例并关闭旧执行器，把完整新包解压到新文件夹，保留 web 文件夹，双击 Start-No-ide.bat。用户配置目录仍沿用原位置；升级前建议备份，避免新旧执行器同时写入。控制台本身不需要安装 Rust 或 Node.js，运行项目仍需要本机对应工具链。

Maven 入口：运行环境 → 构建工具。配置入口：运行台 → 运行配置 → 编辑配置。分组操作：勾选整行/全选 → 底部选择目标分组 → 移动选中文件。

## 边界

这是未签名的开发预览包。Windows Server 2022 CI 不代替用户 Windows 11 人工验收。未自动点击原生 OS 文件选择对话框；没有实跑用户自己的 PMS 工程、企业私服认证或长期压力测试。Spring fixture 通过不代表所有多模块工程和框架版本已全面兼容。JVM 原地 HotSwap、Android 全套部署、clone/checkout、复杂冲突处理及构建产物原子发布仍不是本轮完成项。

本记录只确认上述 Windows 范围，不把一个目标成功写成所有 Linux 发行版或 Mac 架构均已完成验证。GitHub Pages 仍为静态演示，真实操作使用本地运行包。
