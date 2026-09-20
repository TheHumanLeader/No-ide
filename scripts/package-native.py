"""Package the native executable, local web app, notices and dependency lock."""
import pathlib, shutil, sys, zipfile, json, os
root=pathlib.Path(__file__).resolve().parents[1]
label=sys.argv[1]
name='No-ide-v0.3.0-'+label
stage=root/'packages'/name
stage.mkdir(parents=True,exist_ok=True)
exe='no-ide.exe' if label.startswith('windows') else 'no-ide'
shutil.copy2(root/'backend/target/release'/exe,stage/exe)
shutil.copytree(root/'dist',stage/'web',dirs_exist_ok=True)
for source,dest in [('THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.md'),('backend/Cargo.lock','backend-dependency-lock.txt')]:
    if (root/source).is_file():shutil.copy2(root/source,stage/dest)
(stage/'build.json').write_text(json.dumps({'version':'0.3.0','platform':label,'commit':os.environ.get('GITHUB_SHA'),'run':os.environ.get('GITHUB_RUN_ID')},indent=2),encoding='utf-8')
if label.startswith('windows'):
    (stage/'Start-No-ide.bat').write_text('@echo off\r\ncd /d "%~dp0"\r\nno-ide.exe\r\npause\r\n',encoding='ascii')
else:
    launcher=stage/('No-ide.command' if label.startswith('macos') else 'start.sh')
    launcher.write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec ./no-ide\n',encoding='utf-8');launcher.chmod(0o755)
    (stage/exe).chmod(0o755)
(stage/'README.txt').write_text('No-ide 0.3.0 — 本地 Rust 执行器\n\n解压整个目录后启动；web 文件夹必须保留。浏览器由程序自动打开。\nWindows：Start-No-ide.bat；macOS：No-ide.command；Linux：./start.sh。\n不用安装 Rust；运行 Java/Node/Python 项目需要本机已有对应工具链。\n本地默认地址 http://127.0.0.1:17890，其他端口用 --port 指定。\n\nGit / SVN 配置支持：自动检测、选择客户端、手动程序路径、项目覆盖、SVN 配置目录。\nGit/SVN 使用本机命令行客户端，不自动安装，不把密码写入项目配置。\n\n当前为开发预览，未经应用商店签名/公证。请先用测试项目验证，再操作重要代码。\n原地 JVM HotSwap、Android 完整设备部署、clone/checkout、可视化冲突解决尚未实现。\n监听更新为构建后重启；构建失败不主动停止旧进程，但没有隔离第三方构建写入的输出目录。\nGitHub Pages 仍是演示；本运行包启动的是可实际执行的本地版。\n',encoding='utf-8')
with zipfile.ZipFile(root/'packages'/(name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in stage.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(stage.parent))
shutil.rmtree(stage)
