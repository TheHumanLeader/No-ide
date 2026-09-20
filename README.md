# No-ide

**代码交给 AI，运行留在这里。**

面向日常操作和运行结果的轻量工作台。不是另一套网页版 IDEA。

## 当前交付

当前是 **前端交互原型**，还没有 Rust 执行器。

已提供运行台、项目管理、运行记录、环境与设备、设置五个页面。可以体验服务启停、连续改动合并、更新流程、编译失败保留旧版本、重试、日志筛选与导出、错误上下文复制、项目添加、运行配置、快捷搜索、主题和紧凑布局。

所有项目、运行状态、日志、响应和设备均为明确标注的示例。页面不会读取本地项目、启动进程、检测环境或向示例接口发请求。没有实测性能数据。

## 看前端

正式源码使用 **Vue 3 + Quasar QBtn / QToggle + Vite**，不是用其他框架冒充 Quasar。

```bash
npm install
npm run dev
```

开发服务默认仅监听本机。生产构建：

```bash
npm run check
npm run build
npm run preview
```

Node.js 要求：20.19+ 或 22.12+，建议使用 Node.js 22。

### 单文件交互预览

本次会话另交付了 `No-ide-preview.html`，无需运行开发服务器。

在有依赖的环境里，可打包包含真实 Quasar 运行库的离线文件：

```bash
python scripts/build-preview.py --vue node_modules/vue/dist/vue.global.prod.js --quasar-js node_modules/quasar/dist/quasar.umd.prod.js --quasar-css node_modules/quasar/dist/quasar.prod.css --output dist/No-ide-preview.html
```

本次工作容器无法访问 npm / CDN，因此最初交付的离线交互版使用 Vue 运行库和两个标注清楚的兼容控件。该交互版与正式源码共用页面模板、状态逻辑和样式，但它的测试**不等于完整 Quasar 构建测试**。生成脚本要求显式传入 `--offline-controls` 才启用此模式；不会静默替换正式依赖。具体测试范围见 [验证记录](prd/verification.md)。

仓库包含前端构建工作流；是否构建通过，以 GitHub Actions 的实际结果为准，不预先宣称成功。

## 建议体验路径

选择“业务服务” → 模拟代码改动 → 查看构建和更新 → 模拟编译失败 → 在问题面板复制给 AI → 重试更新。

也可以关闭自动更新，再模拟改动，观察待处理状态并手动应用。点击结果预览可以查看明确标注的示例响应。

## 目录

- [产品需求与已确认方案](prd/README.md)
- [运行台设计说明](prd/design/运行台.md)
- [验证记录](prd/verification.md)
- `src/app.js`：页面模板与预览状态适配器。
- `src/styles.css`：明亮粉色 / 星空蓝、响应式布局。
- `src/main.js`：真实 Quasar 入口。
- `scripts/build-preview.py`：单文件打包，支持真实 Quasar 或显式离线兼容模式。
- `tests/interaction-smoke.py`：浏览器交互检查。
- [后续协作规则](AGENTS.md)

## 不做的事

不以模拟数据冒充运行结果；不默认构建全工程索引；不常驻所有语言服务器；不让日志和任务无限堆积；不把 Android 重新部署说成原地热替换。

后端计划：Rust 本地执行器，接管原有 JDK / Maven / Gradle / Node.js / Python / Android SDK。接入后替换预览适配器，保留面向用户的操作与反馈。
