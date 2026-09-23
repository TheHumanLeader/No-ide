"""Publish verified native CI ZIPs to GitHub Releases, without rebuilding.

Only a trusted push/dispatch may call this script. It does not execute artifact
contents, upload test logs, overwrite published assets, or move existing tags.
Requires GitHub CLI and GH_TOKEN with actions:read and contents:write.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

PLATFORMS = {
    'windows-x64': ('Windows x64', 'Start-No-ide.bat'),
    'linux-x64': ('Linux x64 (Ubuntu 22.04 构建基线)', 'start.sh'),
    'macos-arm64': ('macOS Apple Silicon', 'No-ide.command'),
    'macos-x64': ('macOS Intel', 'No-ide.command'),
}
MAX_ARCHIVE = 200 * 1024 * 1024


def gh(*args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(['gh', *args], input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace')[-4000:])
    return result.stdout


def api(path: str, method: str = 'GET', data: dict | None = None):
    args = ['api', '--method', method, path]
    payload = None
    if data is not None:
        args.extend(['--input', '-'])
        payload = json.dumps(data).encode('utf-8')
    return json.loads(gh(*args, data=payload))


def optional_api(path: str):
    try:
        return api(path)
    except RuntimeError as exc:
        if 'HTTP 404' in str(exc):
            return None
        raise


def all_pages(path: str, key: str | None = None) -> list:
    rows = []
    for page in range(1, 101):
        result = api(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
        batch = result[key] if key else result
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise ValueError('Unexpected pagination limit; refusing partial validation')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_members(z: zipfile.ZipFile) -> list[str]:
    names = z.namelist()
    if len(names) != len(set(names)):
        raise ValueError('Duplicate archive members')
    if sum(i.file_size for i in z.infolist()) > MAX_ARCHIVE:
        raise ValueError('Expanded ZIP exceeds release limit')
    for name in names:
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
            raise ValueError(f'Unsafe archive path: {name}')
    if z.testzip() is not None:
        raise ValueError('ZIP CRC verification failed')
    return names


def unpack_verified_package(outer: bytes, version: str, platform: str,
                            commit: str, run: int) -> tuple[str, bytes, dict]:
    expected = f'No-ide-v{version}-{platform}'
    with zipfile.ZipFile(io.BytesIO(outer)) as z:
        names = safe_members(z)
        files = [n for n in names if not n.endswith('/')]
        if files != [expected + '.zip']:
            raise ValueError(f'Unexpected artifact contents: {files}')
        payload = z.read(files[0])
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        names = safe_members(z)
        if any(not n.startswith(expected + '/') for n in names):
            raise ValueError('Native ZIP must have a single versioned directory')
        prefix = expected + '/'
        exe = 'no-ide.exe' if platform == 'windows-x64' else 'no-ide'
        required = [exe, PLATFORMS[platform][1], 'build.json', 'web/index.html',
                    'README.txt', 'THIRD_PARTY_NOTICES.md']
        if tuple(map(int, version.split('-')[0].split('.'))) >= (0, 5, 0):
            required.append('agent/no-ide-agent.jar')
        for name in required:
            if prefix + name not in names:
                raise ValueError('Missing packaged file: ' + name)
        blocked = {'.git', '.svn', '.env', 'settings.json', 'test-results'}
        for name in names:
            p = PurePosixPath(name)
            if blocked.intersection(p.parts) or p.suffix.lower() in {'.ttf', '.otf', '.woff', '.woff2', '.p12', '.pfx', '.pem'}:
                raise ValueError('Unexpected private/font content in release: ' + name)
        build = json.loads(z.read(prefix + 'build.json'))
        expected_build = {'version': version, 'platform': platform, 'commit': commit, 'run': str(run)}
        if any(str(build.get(k)) != str(v) for k, v in expected_build.items()):
            raise ValueError(f'Build provenance mismatch: {build}')
        binary = z.read(prefix + exe)
        if platform == 'windows-x64':
            if binary[:2] != b'MZ':
                raise ValueError('Not a Windows PE executable')
            pe = int.from_bytes(binary[60:64], 'little')
            if binary[pe:pe+6] != b'PE\0\0\x64\x86':
                raise ValueError('Not a Windows x64 executable')
        elif platform == 'linux-x64':
            if binary[:5] != b'\x7fELF\x02' or binary[18:20] != b'\x3e\0':
                raise ValueError('Not a Linux x64 executable')
        else:
            cpu = 0x0100000c if platform == 'macos-arm64' else 0x01000007
            if binary[:4] != b'\xcf\xfa\xed\xfe' or int.from_bytes(binary[4:8], 'little') != cpu:
                raise ValueError('Not the requested Mach-O architecture')
        return expected + '.zip', payload, build


def verify_assets(repo: str, release_id: int, files: list[Path]) -> None:
    assets = all_pages(f'repos/{repo}/releases/{release_id}/assets')
    actual = {a['name']: a for a in assets}
    if set(actual) != {p.name for p in files}:
        raise ValueError('Remote asset names do not match verified release set')
    for p in files:
        a = actual[p.name]
        digest = 'sha256:' + sha256(p.read_bytes())
        if a.get('state') != 'uploaded' or a['size'] != p.stat().st_size:
            raise ValueError('Incomplete remote upload: ' + p.name)
        if a.get('digest'):
            if a['digest'] != digest:
                raise ValueError('Remote asset checksum mismatch: ' + p.name)
        else:
            raw = gh('api', '-H', 'Accept: application/octet-stream',
                     f'repos/{repo}/releases/assets/{a["id"]}')
            if sha256(raw) != digest[7:]:
                raise ValueError('Remote download checksum mismatch: ' + p.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, default=Path('releases/publish.json'))
    parser.add_argument('--run', default='')
    parser.add_argument('--version', default='')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding='utf-8'))
    version = args.version or request['version']
    run_id = int(args.run or request['run_id'])
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', version) or run_id <= 0:
        raise ValueError('Invalid version or run ID')
    repo = os.environ['GITHUB_REPOSITORY']
    if repo != 'TheHumanLeader/No-ide':
        raise ValueError('Publisher is scoped to TheHumanLeader/No-ide')
    run = api(f'repos/{repo}/actions/runs/{run_id}')
    if run['status'] != 'completed' or run['event'] not in {'push', 'workflow_dispatch'}:
        raise ValueError('Only a completed trusted push/dispatch run may be published')
    if run['path'] != '.github/workflows/native.yml' or run['head_repository']['full_name'] != repo:
        raise ValueError('Unexpected build workflow or source repository')
    commit = run['head_sha']
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Invalid source commit')
    jobs = all_pages(f'repos/{repo}/actions/runs/{run_id}/jobs?filter=latest', 'jobs')
    artifacts = all_pages(f'repos/{repo}/actions/runs/{run_id}/artifacts', 'artifacts')
    out = Path('release-out')
    out.mkdir(exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Release output directory is not empty')
    manifest = {'version': version, 'tag': 'v'+version, 'commit': commit, 'run_id': run_id,
                'ci_url': run['html_url'], 'prerelease': True, 'platforms': {}}
    files = []
    for platform, (title, launcher) in PLATFORMS.items():
        matching_jobs = [j for j in jobs if re.fullmatch(r'native \([^,]+, '+re.escape(platform)+r'\)', j['name'])]
        row = {'title': title, 'status': 'unavailable'}
        manifest['platforms'][platform] = row
        if len(matching_jobs) != 1:
            row['reason'] = '没有唯一的平台构建任务'
            continue
        job = matching_jobs[0]
        row.update(job_url=job['html_url'], job_conclusion=job['conclusion'])
        row['skipped_tests'] = [s['name'] for s in job.get('steps', []) if s.get('conclusion') == 'skipped' and any(w in s['name'].lower() for w in ['test', 'regression'])]
        if job['conclusion'] != 'success':
            row['reason'] = '；'.join(s['name'] for s in job.get('steps', []) if s.get('conclusion') in {'failure', 'cancelled', 'timed_out'}) or '平台任务未成功'
            continue
        found = [a for a in artifacts if a['name'] == 'no-ide-'+platform and not a['expired']]
        if len(found) != 1:
            raise ValueError('Successful platform has no unique current package: '+platform)
        artifact = found[0]
        if artifact['workflow_run']['head_sha'] != commit or artifact['size_in_bytes'] > MAX_ARCHIVE:
            raise ValueError('Artifact provenance/size mismatch')
        raw = gh('api', f'repos/{repo}/actions/artifacts/{artifact["id"]}/zip')
        if len(raw) > MAX_ARCHIVE or 'sha256:'+sha256(raw) != artifact.get('digest'):
            raise ValueError('Artifact digest mismatch: '+platform)
        name, payload, build = unpack_verified_package(raw, version, platform, commit, run_id)
        target = out / name
        target.write_bytes(payload)
        files.append(target)
        row.update(status='published', file=name, bytes=len(payload), sha256=sha256(payload),
                   artifact_id=artifact['id'], artifact_digest=artifact['digest'], launcher=launcher)
    if not files:
        raise ValueError('No verified native package; no release created')
    unavailable = [p for p, s in manifest['platforms'].items() if s['status'] != 'published']
    if unavailable and not request.get('allow_partial', False):
        raise ValueError('Some platform checks failed and partial publication is disabled')
    manifest_file = out / 'release-manifest.json'
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    files.append(manifest_file)
    sums = out / 'SHA256SUMS.txt'
    sums.write_text(''.join(f'{sha256(f.read_bytes())}  {f.name}\n' for f in files), encoding='utf-8')
    files.append(sums)
    tag = 'v'+version
    notes = [f'# No-ide {version} · 开发预览版', '',
             '下载下方 Assets 中对应系统的 **No-ide-v…zip**，完整解压后运行。',
             '**Source code (zip/tar.gz) 是源码，不是可执行运行包。**', '',
             '| 平台 | 下载状态 | 启动文件 |', '| --- | --- | --- |']
    for p, row in manifest['platforms'].items():
        status = f'[{row["file"]}](https://github.com/{repo}/releases/download/{tag}/{row["file"]})' if row['status'] == 'published' else '**暂不提供：本次平台任务未通过**'
        notes.append(f'| {row["title"]} | {status} | `{PLATFORMS[p][1]}` |')
    notes.extend(['', '## 版本内容',
                  '- 本地 Rust 执行器与 Quasar 操作台；项目、多实例、多版本运行环境和可视化参数。',
                  '- Maven 模块级增量构建、已删除类/资源清理、Git/SVN Diff 与持久化批量分组。',
                  '- Spring Boot/Maven 可选“优先原地热替换”：支持范围内的方法体改动在原 JVM 内应用；结构性或不支持的改动提示重启，不把重启称作热替换。',
                  '- 旧配置保留兼容模式；启用热替换需停止实例、编辑运行配置并重新启动一次。',
                  '', '## 使用与验证边界',
                  '- 保留 `web/`、`agent/` 及其他随包文件。不需要安装 Rust 或 IDEA；运行工程仍需对应的 Java/Maven/Node.js/Python，版本管理需 Git/SVN 客户端。',
                  '- 升级前停止旧实例并退出旧执行器，备份原有配置后解压到新目录；不要同时运行新旧执行器。',
                  '- 未签名、未公证的开发预览版，不是生产稳定版。不会自动更改系统安全设置。',
                  '- Windows 验证在 Windows Server 2022；macOS ARM64 仅通过其平台原生/编码回归，浏览器与 HotSwap 专项未在 Mac 执行，不能视为完整桌面验收。',
                  '- Linux x64、Intel Mac 缺包时，以以下失败项目为准；没有混入其他版本或未通过任务的包。',
                  '- 不包含用户工程、配置、数据库或业务日志。SHA256SUMS 用于下载完整性校验，不代替代码签名。', '',
                  '## 构建来源', f'- 源码提交：`{commit}`', f'- [原始编译与测试记录]({run["html_url"]})',
                  '- 所有运行 ZIP 均为对应任务生成的原始包；`build.json` 与本页源码提交一致。',
                  '- `release-manifest.json` 列出每个平台任务、跳过的测试、文件摘要及来源。'])
    for p in unavailable:
        row = manifest['platforms'][p]
        notes.append(f'- {row["title"]}：{row["reason"]}。'+(f' [任务详情]({row["job_url"]})' if row.get('job_url') else ''))
    body = '\n'.join(notes)+'\n'
    Path('release-notes.md').write_text(body, encoding='utf-8')
    if args.check_only:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return
    ref_path = f'repos/{repo}/git/ref/tags/{tag}'
    ref = optional_api(ref_path)
    if ref is None:
        api(f'repos/{repo}/git/refs', 'POST', {'ref': 'refs/tags/'+tag, 'sha': commit})
        ref = api(ref_path)
    obj = ref['object']
    if obj['type'] == 'tag':
        obj = api(f'repos/{repo}/git/tags/{obj["sha"]}')['object']
    if obj['type'] != 'commit' or obj['sha'] != commit:
        raise ValueError('Existing tag points elsewhere; refusing to retag')
    release = optional_api(f'repos/{repo}/releases/tags/{tag}')
    if release is None:
        release = api(f'repos/{repo}/releases', 'POST',
                      {'tag_name': tag, 'target_commitish': commit, 'name': f'No-ide {version} · 开发预览版',
                       'body': body, 'draft': True, 'prerelease': True, 'make_latest': 'false'})
    if release['draft']:
        existing = {a['name']: a for a in all_pages(f'repos/{repo}/releases/{release["id"]}/assets')}
        for path in files:
            if path.name not in existing:
                gh('release', 'upload', tag, str(path), '--repo', repo)
        verify_assets(repo, release['id'], files)
        release = api(f'repos/{repo}/releases/{release["id"]}', 'PATCH',
                      {'draft': False, 'prerelease': True, 'body': body, 'make_latest': 'false'})
    else:
        verify_assets(repo, release['id'], files)
    print(release['html_url'])
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(body+'\n公开 Release：'+release['html_url']+'\n')


if __name__ == '__main__':
    main()
