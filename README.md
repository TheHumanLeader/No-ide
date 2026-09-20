# No-ide

**代码交给 AI，运行留在这里。**

面向日常操作和运行结果的轻量工作台。不是另一套网页版 IDEA。

## 当前交付

前端使用 **Vue 3 + Quasar + Vite**。提供运行台、项目管理、运行记录、环境与设备、设置五个页面。支持服务启停、更新流程、连续改动合并、失败保留旧版本、重试、日志筛选与导出、错误上下文复制、项目添加、运行配置、快捷搜索、主题和紧凑布局的交互演示。

**当前为交互原型，Rust 执行器尚未接入。** 项目、运行状态、日志、响应和设备均为明确标注的示例。页面不会读取本地项目、启动进程、检测环境或向示例接口发送请求。没有实测性能数据。

## 直接看前端

本次会话提供 `No-ide-preview.html`：已内嵌真实 Vue / Quasar 运行库，无外部网络依赖。用浏览器打开即可体验，无需安装开发依赖。

正式 Quasar 构建已通过 GitHub Actions，构建产物取回后通过 **25 项 Chromium / Playwright 交互检查**。验证版本：Quasar 2.33.0、Vue 3.5.43、Vite 8.3.0。详见 [验证记录](prd/verification.md)。

建议体验：选择“业务服务” → 模拟代码改动 → 查看构建和更新 → 模拟编译失败 → 复制给 AI → 重试更新。

## 开发与构建

```bash
npm install
npm run dev
```

开发服务默认仅监听本机。建议 Node.js 22.12+。

```bash
npm run check
npm run build
npm run preview
```

生成内嵌真实 Quasar 的单文件：

```bash
python scripts/build-preview.py --vue node_modules/vue/dist/vue.global.prod.js --quasar-js node_modules/quasar/dist/quasar.umd.prod.js --quasar-css node_modules/quasar/dist/quasar.prod.css --output dist/No-ide-preview.html
```

构建工作流输出编译产物、单文件、上游许可证和实际解析的依赖锁。`--offline-controls` 仅保留为显式离线兼容测试选项，最终交付预览不使用该选项。

## 目录

- [产品需求与已确认方案](prd/README.md)
- [运行台设计说明](prd/design/运行台.md)
- [验证记录](prd/verification.md)
- `src/app.js`：页面模板与预览状态适配器。
- `src/styles.css`：明亮粉色 / 星空蓝、响应式布局。
- `src/main.js`：真实 Quasar 入口。
- `src/quasar-overrides.css`：工作台紧凑标题样式。
- `scripts/build-preview.py`：单文件打包。
- `tests/interaction-smoke.py`：浏览器交互检查。
- [后续协作规则](AGENTS.md)

## 后续

Rust 本地执行器接管项目原有 JDK / Maven / Gradle / Node.js / Python / Android SDK。接入后替换预览适配器，保留面向用户的操作和反馈。不默认构建全工程索引，不常驻所有语言服务，不让日志或任务无限堆积。
