"""Package tested native code and web assets. Version comes from Cargo.toml."""
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

解压整个目录，保留 web 文件夹。Windows 双击 Start-No-ide.bat，浏览器自动打开。
macOS：No-ide.command；Linux：./start.sh。
不需要安装 Rust 或 IDEA；运行项目需要本机已有对应的 Java、Node.js、Python 等工具。

升级前先停止旧版实例、关闭旧版启动窗口，然后解压到新文件夹启动。
项目与环境配置保存在系统用户配置目录，不要删除其中的 settings.json。
重要代码先备份。请勿让旧版继续写入新版配置。

本版修复：非 UTF-8 的 Maven 构建输出不再导致启动被误判失败。构建和运行日志兼容 Windows 本地编码；支持高级日志编码选择，路径和版本库结构化数据仍严格校验。
保留整行勾选、Shift 连选、全选/反选和批量分组，不重扫仓库。
运行台直接展示已有配置，可编辑；Maven/Gradle 自动发现和目录选择、Maven settings.xml/仓库设置已加入。

已有能力：
1. 左侧“运行环境”：自动检测，或选择安装目录添加多个 Java / Node.js / Python。
2. 项目运行配置：自动查找常见入口，支持选择模块目录和入口文件。
3. 可视化编辑入参、环境变量、JVM 选项、系统属性，实例可单独选择环境。
4. Git / SVN 代码管理：新建分组，拖动或批量移动文件，重启后记忆归属。
   提交只包含当前组的所选文件。Git 分组提交使用整文件的当前内容，不是逐块提交。
   其他组即使已经暂存，也不会被夹带；提交与推送分开。

客户端路径：项目指定 > 全局指定 > 自动检测；不全盘扫描、不自动安装。
默认仅监听本机 127.0.0.1:17890，可通过 --port 指定端口。
请勿分享带会话令牌的启动地址。GitHub Pages 仍是演示，本地包会真实操作代码。

这是未签名的开发预览包，先在测试工程验证。自动入口识别有范围限制，不代表全量 IDEA 功能。
JVM 原地 HotSwap、Android 完整设备部署、clone/checkout、复杂冲突处理仍未完成。
系统文件选择器的人工桌面验收、私有远端认证与长期性能测试尚未完成。
''',encoding='utf-8')
with zipfile.ZipFile(root/'packages'/(name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in stage.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(stage.parent))
shutil.rmtree(stage)
