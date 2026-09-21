"""SVN .git grouping regression: labels are not VCS writes.
Only temporary repositories. Never reads or changes user code or credentials.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from native_harness import Native, ROOT, cli

checks = []
timings = {}
def check(name, condition=True):
    assert condition, name
    checks.append(name)
    print('PASS', name, flush=True)

def run():
    with Native() as n:
        tools = n.api('tools.detect')
        svn = tools['svn']['selected']['path']
        svnadmin = Path(svn).with_name('svnadmin.exe' if os.name == 'nt' else 'svnadmin')
        if not svnadmin.is_file():
            svnadmin = shutil.which('svnadmin')
        assert svnadmin
        server, wc = n.root/'svn-server', n.root/'SVN mixed work'
        cli(svnadmin, 'create', server)
        cli(svn, 'checkout', server.as_uri(), wc, '--non-interactive')
        (wc/'work.txt').write_text('old\n', encoding='utf8')
        cli(svn, 'add', 'work.txt', cwd=wc)
        cli(svn, 'commit', '-m', 'initial', '--non-interactive', cwd=wc)
        p = n.project(wc, 'SVN 元数据分组验证')
        repo = next(r for r in p['repos'] if r['kind'] == 'svn')
        common = {'project':p['id'], 'repo':repo['id']}
        # Register the SVN working copy before adding another tool's metadata.
        (wc/'.git').mkdir()
        secret = b'[local fixture only]\nsecret=DO_NOT_PREVIEW_THIS\n'
        (wc/'.git/config').write_bytes(secret)
        (wc/'work.txt').write_text('new\n', encoding='utf8')
        before = hashlib.sha256((wc/'.git/config').read_bytes()).hexdigest()
        status = n.api('vcs.status', common)
        assert any(f['path'].replace('\\','/').rstrip('/') == '.git' for f in status['files']), status
        check('SVN lists .git as a local unversioned entry')
        g = n.api('vcs.group.save', {**common, 'name':'忽略不提交'})['items'][-1]
        t = time.monotonic()
        meta = n.api('vcs.group.move', {**common, 'group':g['id'], 'paths':['.git']})
        timings['svn_git_directory_group_ms'] = round((time.monotonic()-t)*1000, 2)
        check('SVN .git directory can be grouped', meta['assignments']['.git'] == g['id'])
        status = n.api('vcs.status', common)
        check('Only ordinary work remains in default', [f['path'] for f in status['files'] if f['group']=='default']==['work.txt'])
        for op in ['add', 'commit']:
            err = n.api('vcs.prepare', {**common, 'operation':op, 'paths':['.git'], 'message':'must not write metadata', 'group':g['id'], 'whole_files':True}, status=400)
            check('Grouping does not permit metadata '+op, '版本库' in err['error'])
        n.api('vcs.diff', {**common, 'path':'.git/config'}, status=400)
        check('API still refuses metadata content access')
        plan = n.api('vcs.prepare', {**common, 'operation':'commit', 'paths':['work.txt'], 'message':'only default', 'group':'default', 'whole_files':True})
        n.api('vcs.execute', {**common, 'token':plan['token'], 'confirmed':True})
        check('Default commit succeeds without .git', cli(svn, 'cat', server.as_uri()+'/work.txt') == 'new')
        check('SVN server contains no .git metadata', '.git' not in cli(svn, 'list', server.as_uri()))
        check('Grouping and default commit leave .git contents byte-identical', before == hashlib.sha256((wc/'.git/config').read_bytes()).hexdigest())
        for invalid in ['../escape', '.git/../../escape', r'..\escape', r'C:\outside', '/outside', r'\\host\share']:
            n.api('vcs.group.move', {**common,'group':g['id'],'paths':[invalid]}, status=400)
        check('Metadata grouping still rejects absolute paths and traversal')
        n.stop(); n.start()
        status = n.api('vcs.status', common)
        check('SVN .git grouping survives actual restart', next(f for f in status['files'] if f['path']=='.git')['group']==g['id'])
        # A .git pointer file and a dangling symbolic name are also label-only.
        (wc/'.git/config').unlink(); (wc/'.git').rmdir(); (wc/'.git').write_bytes(b'gitdir: ../elsewhere\n')
        n.api('vcs.group.move', {**common,'group':'default','paths':['.git']})
        n.api('vcs.group.move', {**common,'group':g['id'],'paths':['.git']})
        check('.git pointer file can be grouped without following its target', (wc/'.git').read_bytes()==b'gitdir: ../elsewhere\n')
        cfg=n.root/'data/settings.json'; n.stop()
        store=json.loads(cfg.read_text(encoding='utf8')); old=store['tools'].get('svn');store['tools']['svn']=str(n.root/'unavailable-svn');cfg.write_text(json.dumps(store), encoding='utf8');n.start()
        n.api('vcs.group.move', {**common, 'group':g['id'], 'paths':['.git', 'nested/.svn', 'nested/.git/config']})
        check('Metadata labels save even when SVN client is unavailable')
        n.stop();store=json.loads(cfg.read_text(encoding='utf8'));store['tools']['svn']=old;cfg.write_text(json.dumps(store), encoding='utf8');n.start()
        if '--browser' in sys.argv:
            browser_test(n, common, g['id'])

def browser_test(n, common, gid):
    from playwright.sync_api import sync_playwright, expect
    n.api('vcs.group.move', {**common,'group':'default','paths':['.git']})
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.set_default_timeout(15000)
        calls=[]; errors=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        def capture(request):
            if request.url.endswith('/api/call'):
                calls.append(request.post_data_json['action'])
        page.on('request',capture)
        page.goto(n.url)
        page.locator('.nav-item').filter(has_text='代码管理').click()
        row=page.locator('.live-file').filter(has=page.get_by_role('checkbox',name='选择 .git',exact=True))
        expect(row).to_have_count(1)
        calls.clear()
        row.locator('.file-row-label').click()
        expect(row.get_by_role('checkbox')).to_be_checked()
        expect(page.locator('.live-diff-body')).to_contain_text('可以勾选并移动')
        check('Clicking SVN .git row selects immediately with safe preview', 'vcs.diff' not in calls)
        page.get_by_label('移动到分组').select_option(gid)
        calls.clear()
        page.get_by_role('button',name='移动选中文件',exact=True).click()
        expect(page.locator('.live-file')).to_have_count(0)
        check('Moving .git sends only one label write', calls == ['vcs.group.move'])
        page.get_by_role('button',name='分组 忽略不提交',exact=True).click()
        expect(page.locator('.live-file')).to_contain_text('.git')
        page.screenshot(path=str(ROOT/'test-results/native-041-svn-git-group.png'),full_page=True)
        page.reload()
        page.locator('.nav-item').filter(has_text='代码管理').click()
        page.get_by_role('button',name='分组 忽略不提交',exact=True).click()
        expect(page.locator('.live-file')).to_contain_text('.git')
        check('Browser reload restores .git group and has no uncaught errors', not errors)
        browser.close()

if __name__=='__main__':
    out=ROOT/'test-results'; out.mkdir(exist_ok=True)
    report={'checks':checks,'timings_ms':timings,'passed':False,'scope':'Real temporary SVN working copy; native picker not automated'}
    try:run();report['passed']=True
    except Exception as e:report['error']=str(e);raise
    finally:(out/('native-metadata-browser.json' if '--browser' in sys.argv else 'native-metadata.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
