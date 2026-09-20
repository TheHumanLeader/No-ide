# v0.3 已知问题

## Intel Mac：首个 Python 实例启动等待超时

受测提交：afb1575b0266b017cb9eba5cd9cda3a3c53ab4f8。

复现：Native executor 工作流，macos-15-intel / macos-x64，tests/backend-smoke.py 第 88 行，第一个 `wait_for(lambda: ready(i1))`。两次执行均在 20 秒等待后超时。

已通过：原生编译、8 项 Rust 测试、本地 HTTP、认证检查、Git/SVN 客户端检测与配置、根目录约束、端口配置校验。

尚未确认：是实例启动、前置构建、就绪检测还是运行环境问题。不能预先归因于机器慢或把单纯延长等待写成已修复。

下一步诊断应在测试失败时归档执行器运行状态与日志，并分别验证前置 Python 构建、程序启动和 TCP 就绪。保留当前失败检查，不能通过跳过此目标或使用模拟结果获得全绿。

本轮不提供该架构的未验证运行包。Apple Silicon Mac、Windows x64、Linux x64 的测试结果独立记录在 verification-v0.3.md。

## 其他范围限制

本地构建更新是构建后重启，不是原地 JVM 热替换。Android 暂时只有构建命令模板；设备枚举、ADB 安装启动、设备日志尚未接入。

SVN 包含 @ 的文件名、目录递归提交和复杂冲突处理目前明确拒绝/未提供。Git clone 与 SVN checkout 未接入本地执行器。

构建失败不主动停止旧进程，但第三方构建程序仍可能改写共享磁盘文件；未实现原子产物切换。参见 native-v0.3.md。
