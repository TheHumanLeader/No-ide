# Windows 日志自动滚动补丁验证

日期：2026-09-21。前端补丁标识：`0.4.2-logfollow.1`。

前端受测源码：`7b4e41733990e4880c31e3de17a8a307347695e9`。
后端复用原 v0.4.2 Windows x64 release，源码 `423c0cfe695784895c9d5b213fdd3da579d87341`，未重新编译、未改 Maven 命令或用户工程。

## 交付物

- `No-ide-v0.4.2-logfollow-web-patch.zip`：190751 字节；SHA-256 `5953a20b43c0be8694dcdaa31293ace5f9b194ec71169ddaee7d1a885b480806`。
- `No-ide-v0.4.2-logfollow-windows-x64.zip`：2295881 字节；SHA-256 `111f0180057c53bf3643d78fbee3403e590e68a9c2978b6cd8aef8ae468fe99f`。

小补丁只含 web 静态资产、说明和前端清单。将 web 合并覆盖到已有 v0.4.2 解压目录，浏览器 Ctrl+F5；不必重配项目或环境。完整包则保留原后端及启动脚本，替换前端，并附加 `frontend-patch.json` 区分前后端来源。完整包使用前先退出旧执行器，避免新旧实例同时运行。

已核对 ZIP CRC、前端资产摘要与入口、包内无字体文件，以及完整包 no-ide.exe 与原版字节相同。EXE SHA-256 为 `c009cd41b526426b6bb8dbfe1246bfde8dcc6bd690a42a52221d2ca5cfc736e5`，PE AMD64；仍为未签名开发预览。界面后端版本仍显示 v0.4.2，可通过日志区新增的“自动滚动”与“回到底部”识别补丁。

## 修复与实现边界

原生运行台日志区域原来没有自动定位滚动逻辑。现在默认跟随最新输出；手动向上翻、PageUp/Home 或关闭自动滚动后，保留当前文本与滚动位置。回到底部、End、重新启用自动滚动或继续展示会追上最新输出。

日志记录而非数组长度触发更新，避免最近 120 条窗口长度不变时不滚动。等待 Vue 完成 DOM 更新后同步定位，仅滚动日志区域，不使用 scrollIntoView 拉动整个页面，不使用平滑动画追赶不断输出的日志。ResizeObserver 处理长行换行与尺寸变化，并在组件卸载时清理。不会增加常驻轮询。

上翻阅读或暂停展示期间保留一份最多 1000 条的快照，前端原有收集缓冲同样最多 1000 条，界面最多渲染最近 120 条。新日志淘汰旧缓冲时，不改变用户正在阅读的文本。没有在本轮添加完整日志归档功能。

## 真实 Windows 验证

工作流：https://github.com/TheHumanLeader/No-ide/actions/runs/35572474673
Windows 任务：106247065357。

生产前端依赖安装、语法检查、原有 npm 测试与 Vite 构建成功。随后在 Windows Server 2022 上，以原版 v0.4.2 二进制和新生产前端运行 `tests/log-scroll.py`。

测试使用一次性本机 Python 进程产生真实标准输出，经 Rust 后端、真实 WebSocket、Vue/Quasar 到实际 DOM 的 scrollTop；未伪造 API 或日志响应。共 23 项检查通过，无未捕获浏览器异常。

覆盖首次快照自动到底部、默认开启、120 条窗口滚动、外层页面位置不变、手动上翻保留文本与位置、回到底部后继续跟随、暂停/继续、PageUp/End、自动滚动开关、筛选与空结果、长行换行/窗口大小变化、手机无横向溢出、拖动滚动条返回底部、切换页面、超过 1000 条后的有界 DOM、切换项目和刷新页面。已读报告并查看真实 Windows 跟随状态和阅读状态截图。

第一次验证发现第二个 requestAnimationFrame 会抢回手动滚动，已修为 Vue DOM 更新后同步定位；第二次验证的导航定位误用了不含图标的完整 accessible name，已改为实际导航元素定位。没有删除滚动断言或把失败报告改为成功。

## 与 IDEA 启动内容不同：仍待定位，不属于此补丁已解决的问题

已检查当前 `backend/src/launch.rs`：spring-maven 只在选定配置 cwd 中执行 `-DskipTests compile` 和 `spring-boot:run`，没有自动从聚合根构建同工程依赖模块。因此存在入口模块新、同工程依赖来自 Maven 本地仓库旧 JAR 的风险。

但本次对话尚未收到两份可对照的 IDEA/No-ide 完整启动日志；不能确认用户所说“版本置后”就是上述风险实际发生，也不能把 Maven compiler/resources 插件版本当作业务应用版本。应对照实际 JDK、工作目录、主类和 classpath、配置文件、Spring/Maven profiles、端口与业务差异。

此补丁仅解决滚动，明确不修复多模块产物来源问题；不升级 Spring Boot/JDK/依赖、不清空 .m2、不改系统编码或用户路径。后续多模块验收必须预置旧的同工程依赖 JAR，再改该模块源码，通过实际接口验证新代码被加载；不能只看进程存在或编译退出码。

参考：
- Maven reactor：https://maven.apache.org/guides/mini/guide-multiple-modules.html
- IDEA 构建行为：https://www.jetbrains.com/help/idea/compiling-applications.html

上述 Windows CI 不等于已运行用户 PMS、Windows 11 桌面或企业私服。其他平台没有在本轮追加验证。此前日志编码、多版本运行环境和分组功能保持原后端行为。
