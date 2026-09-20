# No-ide

**代码交给 AI，运行留在这里。**

[打开在线工作台](https://thehumanleader.github.io/No-ide/) · Vue 3 / Quasar · 前端交互原型 v0.2

## 这次怎么用

- **项目 → 运行配置 → 多个实例**：一个项目可以同时组织多个 Java 服务、同一 Java 服务的两个实例和一个 Vite。实例独立启停、端口和参数独立；公共运行命令只配置一次。
- **创建项目先选文件夹**：点击项目管理 → 创建项目 → 选择文件夹。名称可直接使用目录名，不必手写路径。新项目默认没有实例，不塞入示例服务。
- **代码管理**：项目可包含多个 Git / SVN 仓库根目录。选择文件查看并排或统一 Diff。Git 是暂存 → 本地提交 → 单独推送；SVN 是勾选文件 → 直接提交到服务器。拉取 / 更新和提交均有独立反馈及确认。

从“示例商城”开始，可体验 6 个运行配置、7 个实例、Git 主仓库和 SVN 公共组件库。“空白实验项目”用于体验空状态和添加实例。

## 当前边界

这是**可操作前端，不是真实执行器**。实例启停、热更新、Git / SVN 拉取、提交和推送均是明确标注的演示，不会修改磁盘或访问仓库。Rust 本地执行器尚未实现。

目录按钮会请求浏览器目录选择器，只记录目录名称，不遍历、读取或上传文件。浏览器不会提供可直接交给本地进程的绝对路径；完整目录定位待执行器接入。兼容选择器可能枚举文件条目，页面会提示；不会读取文件内容。

“从仓库获取”只记录 clone / checkout 意图，目前不会下载代码。用户自己选择的项目不会获得虚构的仓库差异。

项目、实例、仓库变更和提交记录仅保留在本次预览会话；刷新恢复示例。外观与自动更新偏好保存在浏览器。

## 开发

```bash
npm install
npm run check
npm test
npm run dev
```

建议 Node.js 22.12+。正式构建：`npm run build`；预览构建：`npm run preview`。开发与预览服务默认仅监听本机。

生成包含真实 Vue / Quasar 的离线单文件：

```bash
python scripts/build-preview.py --vue node_modules/vue/dist/vue.global.prod.js --quasar-js node_modules/quasar/dist/quasar.umd.prod.js --quasar-css node_modules/quasar/dist/quasar.prod.css --output dist/No-ide-preview.html
```

工作流负责检查、模型测试、构建及 GitHub Pages 部署；是否上线以对应 Actions 部署步骤实际成功为准。

## 文档与测试

- [产品需求](prd/README.md)
- [v0.2 项目、多实例与版本管理](prd/project-instance-vcs.md)
- [v0.2 验证记录](prd/verification-v0.2.md)
- [v0.1 验证历史](prd/verification.md)
- [协作规则](AGENTS.md)

源码拆分为 `app.js`（运行状态）、`layout.html`（操作界面）、`project-model.js`（项目实例与目录选择）、`source-control.js`（示例版本管理和有界文本 Diff）。`main.js` 为真实 Quasar 入口。
