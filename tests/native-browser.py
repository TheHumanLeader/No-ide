"""Exercise real Vite UI and Rust executor using disposable local fixtures."""
import json, os, pathlib, shutil, signal, socket, subprocess, tempfile, time, urllib.request, urllib.parse
from playwright.sync_api import sync_playwright, expect
ROOT=pathlib.Path(__file__).resolve().parents[1]
EXE=pathlib.Path(os.environ.get('NO_IDE_TEST_EXE',str(ROOT/'backend/target/release/no-ide')))
WEB=pathlib.Path(os.environ.get('NO_IDE_TEST_WEB',str(ROOT/'dist')))
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
checks=[];errors=[]
def check(name):checks.append(name);print('PASS',name,flush=True)
with tempfile.TemporaryDirectory(prefix='no-ide-ui-') as temp:
    temp=pathlib.Path(temp);startup=temp/'startup.log';project=temp/'ui project';project.mkdir()
    git=shutil.which('git')
    def cli(*a):return subprocess.check_output([git,*a],cwd=project,stderr=subprocess.STDOUT).decode()
    cli('init','-b','main');cli('config','user.name','Native UI test');cli('config','user.email','ui@example.invalid')
    (project/'sample.txt').write_text('old line\n',encoding='utf8');cli('add','.');cli('commit','-m','initial')
    log=startup.open('w');proc=subprocess.Popen([str(EXE),'--no-open','--port','0','--data-dir',str(temp/'data'),'--web-dir',str(WEB)],stdout=log,stderr=subprocess.STDOUT)
    api=None
    try:
        url=None
        for _ in range(100):
            text=startup.read_text()
            if 'NO_IDE_URL=' in text:url=text.split('NO_IDE_URL=',1)[1].splitlines()[0];break
            if proc.poll() is not None:raise RuntimeError(text)
            time.sleep(.1)
        assert url
        base=url.split('#')[0].rstrip('/');token=urllib.parse.parse_qs(urllib.parse.urlparse(url).fragment)['token'][0]
        def api(action,params={}):
            req=urllib.request.Request(base+'/api/call',data=json.dumps({'action':action,'params':params}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            return json.load(urllib.request.urlopen(req,timeout=60))
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1040});page.set_default_timeout(15000)
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url);expect(page.locator('.live-workbench')).to_be_visible();expect(page.locator('.live-real-badge')).to_have_text('真实运行');check('Real native adapter loads, not mock UI')
            expect(page.locator('.live-empty')).to_contain_text('没有示例项目');check('Empty local state has no mock data')
            page.locator('.nav-item').filter(has_text='Git / SVN 配置').click()
            expect(page.locator('.live-client-result').first).to_contain_text('git version',timeout=30000);check('Actual Git discovery shown')
            page.screenshot(path=str(OUT/'native-tools.png'),full_page=True)
            project_data=api('project.add',{'root':str(project),'name':'本地验证项目','confirmed':True})
            page.get_by_role('button',name='刷新状态',exact=True).click();page.locator('.nav-item').filter(has_text='运行台').click()
            expect(page.locator('.live-project-select')).to_have_value(project_data['id']);check('Persisted project appears in UI')
            page.get_by_role('button',name='＋ 运行配置',exact=True).click()
            expect(page.get_by_role('dialog')).to_be_visible();check('Run configuration editor opens')
            inputs=page.locator('.live-modal input')
            inputs.nth(0).fill('Python 验证服务');inputs.nth(1).fill('.')
            inputs.nth(2).fill(shutil.which('python3') or shutil.which('python'))
            page.locator('.live-modal textarea').first.fill('-u\n-m\nhttp.server\n{port}\n--bind\n127.0.0.1')
            page.get_by_role('button',name='保存配置',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0);check('UI saves actual executable configuration')
            page.get_by_role('button',name='＋ 添加实例',exact=True).click();page.locator('.live-modal input').first.fill('真实实例 01')
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            page.locator('.live-modal input[type=number]').fill(str(port));page.get_by_role('button',name='保存实例',exact=True).click()
            expect(page.locator('.live-instance')).to_have_count(1);check('Instance persists through API')
            page.locator('.live-instance').get_by_role('button',name='运行',exact=True).click()
            expect(page.locator('.live-instance-status .status')).to_have_text('运行中',timeout=25000)
            expect(page.locator('.live-instance-status')).to_contain_text('PID');check('Run button starts actual process and reports PID')
            assert b'sample.txt' in urllib.request.urlopen(f'http://127.0.0.1:{port}').read();check('Started app serves real HTTP response')
            page.screenshot(path=str(OUT/'native-running.png'),full_page=True)
            page.locator('.live-instance').get_by_role('button',name='停止实例',exact=True).click()
            expect(page.locator('.live-instance-status .status')).to_have_text('已停止');check('Stop button stops actual process')
            (project/'sample.txt').write_text('new native UI line\n',encoding='utf8')
            page.locator('.nav-item').filter(has_text='代码管理').click()
            page.locator('.live-file button').filter(has_text='sample.txt').first.click()
            expect(page.locator('.live-diff-body')).to_contain_text('+new native UI line');check('Diff comes from real Git worktree')
            page.get_by_role('button',name='并排',exact=True).click();expect(page.locator('.live-diff-body')).to_have_class('live-diff-body split');check('Native Diff view toggles')
            page.screenshot(path=str(OUT/'native-diff.png'),full_page=True)
            page.get_by_role('checkbox',name='选择 sample.txt',exact=True).check()
            page.get_by_role('button',name='暂存选中',exact=True).click();expect(page.get_by_role('dialog')).to_contain_text('sample.txt');check('Stage requires operation review')
            page.get_by_role('button',name='确认执行',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
            assert 'sample.txt' in cli('diff','--cached','--name-only');check('Stage button modifies real Git index')
            page.locator('.live-commit textarea').fill('native browser verified')
            page.get_by_role('button',name='检查并提交暂存区',exact=True).click();expect(page.get_by_role('dialog')).to_contain_text('仅提交到本地仓库，不推送');check('Commit dialog names local destination')
            page.get_by_role('button',name='确认执行',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
            assert cli('log','-1','--format=%s').strip()=='native browser verified';check('Commit button creates real local commit')
            page.reload();expect(page.locator('.live-instance')).to_have_count(1);check('Project and instance survive reload')
            page.set_viewport_size({'width':390,'height':844});page.locator('.nav-item').filter(has_text='Git / SVN 配置').click()
            expect(page.locator('.live-tools')).to_be_visible();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');check('Mobile configuration has no horizontal overflow')
            page.screenshot(path=str(OUT/'native-mobile.png'),full_page=True)
            assert not errors,errors;check('No uncaught browser exception')
            browser.close()
    finally:
        (OUT/'native-browser.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'scope':'Actual Vite UI + Rust binary; native OS dialog not automated'},ensure_ascii=False,indent=2),encoding='utf8')
        if api:
            try:
                for pp in api('state')['store']['projects']:
                    for ii in pp['instances']:
                        try:api('run.stop',{'project':pp['id'],'instance':ii['id']})
                        except Exception:pass
            except Exception:pass
        proc.send_signal(signal.SIGINT)
        try:proc.wait(timeout=8)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()
print('PASSED',len(checks))
