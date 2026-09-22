"""Package native code and production assets; callers must first pass CI tests."""
import pathlib, shutil, sys, zipfile, json, os, tomllib
root=pathlib.Path(__file__).resolve().parents[1]
label=sys.argv[1]
version=tomllib.loads((root/'backend/Cargo.toml').read_text(encoding='utf-8'))['package']['version']
name='No-ide-v'+version+'-'+label
stage=root/'packages'/name
stage.mkdir(parents=True,exist_ok=True)
exe='no-ide.exe' if label.startswith('windows') else 'no-ide'
shutil.copy2(root/'backend/target/release'/exe,stage/exe)
shutil.copytree(root/'dist',stage/'web',dirs_exist_ok=True)
(stage/'agent').mkdir(exist_ok=True)
shutil.copy2(root/'agent/target/no-ide-agent.jar',stage/'agent/no-ide-agent.jar')
shutil.copy2(root/'agent/src/main/resources/META-INF/ASM-LICENSE.txt',stage/'agent/ASM-LICENSE.txt')
for source,dest in [('THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.md'),('backend/Cargo.lock','backend-dependency-lock.txt')]:
    if (root/source).is_file():shutil.copy2(root/source,stage/dest)
(stage/'build.json').write_text(json.dumps({'version':version,'platform':label,'commit':os.environ.get('GITHUB_SHA'),'run':os.environ.get('GITHUB_RUN_ID')},indent=2),encoding='utf-8')
if label.startswith('windows'):
    (stage/'Start-No-ide.bat').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nno-ide.exe\r\npause\r\n')
else:
    launcher=stage/('No-ide.command' if label.startswith('macos') else 'start.sh')
    launcher.write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec ./no-ide\n',encoding='utf-8');launcher.chmod(0o755)
    (stage/exe).chmod(0o755)
(stage/'README.txt').write_text(f'''No-ide {version} — 本地 Rust 执行器

完整解压，保留 web 和 agent 文件夹。Windows 双击 Start-No-ide.bat，浏览器自动打开。
macOS：No-ide.command；Linux：./start.sh。
不需安装 Rust 或 IDEA；运行工程仍需本机已有对应 Java / Maven / Node.js / Python。

升级：先停止旧实例、退出旧执行器，再解压到新目录启动。备份系统用户配置目录中的 no-ide 配置，不删除 settings.json，不同时运行新旧执行器。

本版 Maven：首次建立可信构建基线，之后默认只重编源码或产物变化的模块及其下游依赖者；未变上游模块复用。按内容指纹核对，不仅看文件修改时间。停止或退出后保留指纹。
删除类、内部类、资源时清理受影响模块，不清理整条上游依赖链。源码不变但产物被删除或替换，也会重新检查。
日常点“应用改动”。“清理重建”是独立、需确认的完整修复操作。
首次建立基线、POM / JDK / Maven / 构建环境变化、未知自定义生命周期输入时仍可能保守重建，日志明确列出原因、重编和复用范围。
首次使用额外的 Maven help/dependency 官方插件读取有效模型和依赖清单，不修改项目 POM。插件由所选 Maven settings 配置的仓库解析。
这是模块级增量，不是仅编译一个 Java 文件。
Spring Boot / Maven 可选“优先原地热替换”：构建后直接启动所选 Java 和内置 Agent，使用私有输出与依赖快照。
原配置保留兼容模式；停止实例 → 编辑配置 → 代码更新方式选择“优先原地热替换” → 保存并启动一次。
之后点击“应用改动”，支持的已加载方法体变更在相同 JVM 内生效，不重新初始化应用。
新增/删除类、字段、方法，注解、资源、初始化逻辑、未加载类、自定义类加载器或依赖变更会提示需重启；不会自动重启。
点击“重启实例”会检查当前源码后使用最新输出，仅重启该实例；“清理重建”需确认，属于修复操作。
本进程禁用 DevTools 自动重启，避免与原地替换重复处理。其他 Agent / 调试器 / 复杂插件类路径当前不兼容，会明确报错；可选回兼容模式。
正在执行的方法调用可能继续旧方法体；已有对象字段值不重新初始化；任意一次性逻辑不会自动重新执行。
初次建立模型/私有副本与首次启动仍需时间，不承诺任意工程秒级。
程序不会把用户项目日志上传到网络。

保留：聚合根构建本地依赖、独立应用工作目录、UTF-8 / Windows 本地日志编码、多环境选择、可视化参数、Git/SVN 整行批量勾选与持久分组、日志自动跟随。
高阶自定义原始命令仍按用户命令执行，不替用户改写脚本。
源码、类路径、生成器和外部输入复杂时可能不能安全复用，本版不会把未知状态当作“最新”。热替换模式的 classpath 使用私有副本；兼容模式仍使用原构建目录。业务自行读取的外部配置/数据不在隔离范围，多 JVM 更新不是跨进程事务。

只绑定本机 127.0.0.1:17890；可用 --port 调整。不要分享含会话令牌的启动地址。GitHub Pages 为演示，本机包真实操作代码。
构建中的 install 更新本地 Maven 仓库，不是 Git/SVN 提交或远程 deploy。
未签名开发预览。系统文件选择器、私服定制和长期运行需用户环境验证。具体平台通过范围见相应 CI 报告，不能把单个平台通过当成全平台验收。
''',encoding='utf-8')
with zipfile.ZipFile(root/'packages'/(name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in stage.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(stage.parent))
shutil.rmtree(stage)
