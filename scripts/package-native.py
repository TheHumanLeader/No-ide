"""Package a native executable together with the locally served Quasar app."""
import pathlib, shutil, sys, zipfile
root=pathlib.Path(__file__).resolve().parents[1]
label=sys.argv[1]
name='No-ide-v0.3.0-'+label
stage=root/'packages'/name
stage.mkdir(parents=True,exist_ok=True)
exe='no-ide.exe' if label.startswith('windows') else 'no-ide'
shutil.copy2(root/'backend/target/release'/exe,stage/exe)
shutil.copytree(root/'dist',stage/'web',dirs_exist_ok=True)
if label.startswith('windows'):
    (stage/'Start-No-ide.bat').write_text('@echo off\r\ncd /d "%~dp0"\r\nno-ide.exe\r\npause\r\n',encoding='ascii')
else:
    launcher=stage/('No-ide.command' if label.startswith('macos') else 'start.sh')
    launcher.write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec ./no-ide\n',encoding='utf-8');launcher.chmod(0o755)
    (stage/exe).chmod(0o755)
(stage/'README.txt').write_text('No-ide 0.3.0 — 本地 Rust 执行器\n解压整个目录后启动；web 文件夹必须保留。\n本地地址默认 http://127.0.0.1:17890，浏览器由程序自动打开。\nGit/SVN 使用本机客户端，不自动安装。\n这是开发预览，未经应用商店签名/公证。\n',encoding='utf-8')
with zipfile.ZipFile(root/'packages'/(name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in stage.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(stage.parent))
shutil.rmtree(stage)
