"""Append a version-specific note only after the existing publisher verified assets.
Does not upload binaries, move tags, or change release visibility.
"""
import json
import os
from pathlib import Path
import re
from publish_release import api


def compose(base: str, extra: str) -> str:
    if not extra.strip():
        return base
    section = '\n## 本次更新\n\n' + extra.strip() + '\n\n'
    # Base is generated fresh by the publisher, so repeat execution is idempotent.
    before, separator, after = base.partition('\n## 版本内容\n')
    return before + section + ('## 版本内容\n' + after if separator else '')


def main() -> None:
    root = Path.cwd()
    manifest = json.loads((root / 'release-out/release-manifest.json').read_text(encoding='utf-8'))
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?', version):
        raise ValueError('Invalid verified release version')
    extra = root / 'releases' / ('v' + version + '.md')
    if not extra.is_file():
        print('No version-specific notes; verified release unchanged.')
        return
    repo = os.environ['GITHUB_REPOSITORY']
    if repo != 'TheHumanLeader/No-ide':
        raise ValueError('Unexpected repository')
    release = api(f'repos/{repo}/releases/tags/v{version}')
    if release['draft'] or release['target_commitish'] != manifest['commit']:
        raise ValueError('Release no longer matches verified publication')
    base = (root / 'release-notes.md').read_text(encoding='utf-8')
    body = compose(base, extra.read_text(encoding='utf-8'))
    result = api(f'repos/{repo}/releases/{release["id"]}', 'PATCH', {'body': body})
    if result.get('body') != body:
        raise ValueError('Release notes did not persist')
    (root / 'release-notes.md').write_text(body, encoding='utf-8')
    print(result['html_url'])


if __name__ == '__main__':
    main()
