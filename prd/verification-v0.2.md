# v0.2 · 验证记录

日期：2026-09-20。仅记录实际检查与明确边界；不将演示当作真实热运行或仓库操作。

## 已完成的本地检查

JavaScript 语法检查通过。包含真实 Quasar / Vue 的单文件通过 36 项 Chromium / Playwright 检查，renderer 为 quasar，未捕获脚本错误为 0；测试期间未发送网络请求。检查源码见 `tests/interaction-v2.py`，旧 `interaction-smoke.py` 入口转发到本版。

覆盖：项目 / 配置 / 实例层级、同配置多实例独立运行与停止、失败保留旧版、重试、端口冲突、批量实例、公共命令共享但端口独立、空项目、新 Vite 配置、项目启停及日志隔离、目录选择成功 / 取消 / 拒绝与兼容分支、远程获取待执行、Git 统一 / 并排 Diff、脏工作区阻止拉取、只提交暂存文件、推送单独确认、SVN 勾选提交与无 push 语义、冲突阻止、项目仓库状态隔离。

1440 / 1024 / 768 / 390 像素视口的运行台和代码管理页均无页面级横向溢出；已查看桌面和移动端截图。Diff 面板自身可滚动，不将内容裁切冒充适配。

## 目录测试的准确含义

showDirectoryPicker 的成功、取消和权限失败采用受控测试替身，验证页面处理分支；兼容选择使用 Playwright 文件输入注入。没有完成操作系统原生目录对话框、用户 Windows / Edge 环境或本地执行器的端到端测试。

页面测试通过 about:blank + set_content 加载完整 HTML，非线上 URL 的直接浏览器复验。不宣称现场网站按钮已测。最终依赖安装、模型测试、Vite 构建和 Pages 部署由 GitHub Actions 执行，状态以对应提交的真实运行记录为准。

## 模型测试

`npm test` 包含 5 个测试：共享配置与实例覆盖、端口验证、Diff 重建双方文本、Diff 输入上限、示例仓库状态独立。尚未运行或未通过时不得宣称成功；CI 在构建前执行此命令。

## 仍未实现 / 未验证

Rust 进程管理、真实共享构建、源码监听与热替换、真实 Git / SVN 检测 / 拉取 / 提交 / 推送、真实冲突解决、凭据管理、系统文件选择与绝对路径、CPU / 内存和长时间性能测量。

项目和仓库状态当前仅在内存中保存，刷新还原示例。单文件预览使用真实 Quasar，不以兼容控件替代。

## 重现

```bash
npm install
npm run check
npm test
npm run build
# 安装 Python Playwright 与 Chromium 后，给定单文件：
python tests/interaction-v2.py --html No-ide-preview.html --output test-results/v2
```
