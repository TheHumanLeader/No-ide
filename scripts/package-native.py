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

完整解压，保留 web 文件夹。Windows 双击 Start-No-ide.bat，浏览器自动打开。
macOS：No-ide.command；Linux：./start.sh。
不需安装 Rust 或 IDEA；运行工程仍需本机已有对应 Java / Maven / Node.js / Python。

升级：先停止旧实例、退出旧执行器，再解压到新目录启动。备份系统用户配置目录中的 no-ide 配置，不删除 settings.json，不同时运行新旧执行器。

本版 Maven：首次建立可信构建基线，之后默认只重编源码或产物变化的模块及其下游依赖者；未变上游模块复用。按内容指纹核对，不仅看文件修改时间。停止或退出后保留指纹。
删除类、内部类、资源时清理受影响模块，不清理整条上游依赖链。源码不变但产物被删除或替换，也会重新检查。
日常点“增量构建”。“清理重建”是独立、需确认的完整修复操作。
首次建立基线、POM / JDK / Maven / 构建环境变化、未知自定义生命周期输入时仍可能保守重建，日志明确列出原因、重编和复用范围。
首次使用额外的 Maven help/dependency 官方插件读取有效模型和依赖清单，不修改项目 POM。插件由所选 Maven settings 配置的仓库解析。
这是模块级增量，不是仅编译一个 Java 文件；仍通过 Maven 启动 Spring Boot，不是 JVM 原地热替换。Spring 初始化时间独立存在，不能保证秒级启动。

保留：聚合根构建本地依赖、独立应用工作目录、UTF-8 / Windows 本地日志编码、多环境选择、可视化参数、Git/SVN 整行批量勾选与持久分组、日志自动跟随。
高阶自定义原始命令仍按用户命令执行，不替用户改写脚本。
源码、类路径、生成器和外部输入复杂时可能不能安全复用，本版不会把未知状态当作“最新”。产物尚非隔离构建或原子发布，旧进程仍可能看到共享磁盘产物变化。

只绑定本机 127.0.0.1:17890；可用 --port 调整。不要分享含会话令牌的启动地址。GitHub Pages 为演示，本机包真实操作代码。
构建中的 install 更新本地 Maven 仓库，不是 Git/SVN 提交或远程 deploy。
未签名开发预览。系统文件选择器、私服定制和长期运行需用户环境验证。具体平台通过范围见相应 CI 报告，不能把单个平台通过当成全平台验收。
''',encoding='utf-8')
with zipfile.ZipFile(root/'packages'/(name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in stage.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(stage.parent))
shutil.rmtree(stage)
