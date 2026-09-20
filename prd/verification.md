# 前端验证记录

日期：2026-09-20。

## 实际完成

- `node --check src/app.js` 通过。
- `node --check src/main.js` 通过。
- 单文件离线交互版通过 25 项 Chromium / Playwright 检查，无未捕获浏览器异常。
- 已检查 1440、1024、768、390 像素视口，页面无横向溢出；已查看桌面与手机截图。

测试覆盖初始六服务、搜索筛选、更新版本、失败保留旧版、复制降级、重试、停止后不恢复、自动更新关闭与手动应用、示例响应边界、配置保存、快捷搜索、添加项目、主题、紧凑布局、工具未检测、示例设备、项目页、运行记录和响应式导航。

## 测试方式与限制

工作容器无法从 npm / CDN 下载依赖。本地已有 Vue 3.5.13，离线预览显式使用两个兼容控件代替 QBtn / QToggle，其他模板、状态逻辑和样式与正式源码共享。

因此：**25 项测试是离线交互版验证，不是完整 Quasar 构建验证。** 正式源码在 `src/main.js` 中导入真实 Quasar。没有伪造 `npm install`、`npm run build` 或 GitHub Actions 成功记录。

工作容器浏览器不允许直接导航 file URL，所以测试用 Playwright `set_content` 注入完整 HTML。文件无外部依赖，交付为单文件；仍未在用户本机 Windows / Edge 的 file URL 上实测。浏览器禁止 localStorage 时会安全退回不持久化模式；剪贴板无权限时显示手动复制文本。

GitHub Actions 工作流将安装真实依赖、检查并构建前端，再输出包含真实 Quasar 的单文件预览。实际运行结果以对应 Actions 记录为准。

## 明确未验证

真实编译 / 热替换 / 进程树管理、真实 Android 安装部署、真实 HTTP 请求、实际 CPU / 内存 / 时延，以及连续长时间运行测试。Rust 执行器尚未实现。

## 重现交互检查

安装 Python 的 Playwright 和 Chromium 后：

```bash
python tests/interaction-smoke.py --html No-ide-preview.html --output test-results
```

脚本报告会记录实际使用的 renderer，避免将兼容模式误认成 Quasar。
