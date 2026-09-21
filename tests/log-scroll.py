"""Real browser + native stdout/WebSocket regression for the log-follow patch.
Only temporary projects/settings; no fake API/log responses and no user files.
"""
import json, os, pathlib, shutil, sys, time
from playwright.sync_api import sync_playwright, expect
from native_harness import Native, ROOT, wait_for
OUT = ROOT / 'test-results'
OUT.mkdir(exist_ok=True)
report = {'scope': 'real native stdout -> WebSocket -> production Vue/Quasar -> scroll position',
          'platform': sys.platform, 'checks': [], 'errors': [], 'passed': False}

def check(name, condition=True):
    assert condition, name
    report['checks'].append(name)
    print('PASS', name, flush=True)

def main():
    with Native() as n:
        root = n.root / 'log project'; root.mkdir()
        command = root / 'emit.json'
        command.write_text('{"count":240}', encoding='utf8')
        script = root / 'producer.py'
        script.write_text('''import json, pathlib, sys, time
count=0
while True:
 try: target=json.loads(pathlib.Path('emit.json').read_text())['count']
 except (ValueError, OSError): time.sleep(.02);continue
 if count < target:
  count+=1
  marker=' NEEDLE' if count%10==0 else ''
  tail=' wrapped-text'*28 if count%7==0 else ''
  print('LOG%05d%s%s'%(count,marker,tail),flush=True)
  time.sleep(.008)
 else: time.sleep(.02)
''', encoding='utf8')
        project = n.project(root, '日志自动滚动回归')
        c = n.api('config.save', {'project':project['id'], 'config':{
            'id':'','name':'真实日志输出','cwd':'.','command':{'program':sys.executable,'args':['-u',str(script)]},
            'build':None,'watch':[],'env':{}}})
        instance = n.api('instance.save', {'project':project['id'],'instance':{
            'id':'','name':'日志实例','config_id':c['id'],'args':[],'env':{}}})
        n.api('run.start', {'project':project['id'],'instance':instance['id']})
        wait_for(lambda:any('LOG00240' in l['text'] for l in n.api('logs')), 30)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium') or None, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1440,'height':1100})
            page.set_default_timeout(15000)
            page.on('pageerror', lambda e:report['errors'].append(str(e)))
            page.goto(n.url)
            panel = page.locator('.live-log-panel')
            body = page.locator('.live-log-body')
            rows = page.locator('.live-log-row')
            auto = page.get_by_label('自动滚动日志', exact=True)
            def bottom():
                page.wait_for_function("""() => {const e=document.querySelector('.live-log-body');
                    return e && e.scrollHeight-e.clientHeight-e.scrollTop<=3} """)
            def emit(count, displayed=True):
                command.write_text(json.dumps({'count':count}), encoding='utf8')
                marker=f'LOG{count:05}'
                wait_for(lambda:any(marker in l['text'] for l in n.api('logs')),30)
                if displayed: expect(body).to_contain_text(marker)
            def viewport_state():
                return body.evaluate('(e)=>({top:e.scrollTop,rows:e.innerText})')
            expect(body).to_contain_text('LOG00240');bottom()
            check('Initial WebSocket snapshot opens at the latest log')
            expect(auto).to_be_checked()
            check('Auto scrolling is on by default')
            expect(rows).to_have_count(120)
            emit(400);bottom();expect(rows).to_have_count(120)
            check('Rolling 120-record window follows even when its length never changes')
            page.evaluate('window.scrollTo(0,0)'); y=page.evaluate('window.scrollY')
            emit(480);bottom()
            check('Following moves only the log panel, never the outer page',page.evaluate('window.scrollY')==y)
            body.scroll_into_view_if_needed();body.hover();page.mouse.wheel(0,-450)
            expect(auto).not_to_be_checked();page.wait_for_timeout(160)
            saved=viewport_state();emit(560,False);page.wait_for_timeout(150)
            check('Scrolling up holds exactly the viewed text and position',viewport_state()==saved)
            expect(page.get_by_role('button',name='回到底部并恢复自动滚动')).to_be_visible()
            check('A clear back-to-bottom control appears while reviewing')
            page.get_by_role('button',name='回到底部并恢复自动滚动').click()
            expect(auto).to_be_checked();expect(body).to_contain_text('LOG00560');bottom()
            emit(640);bottom()
            check('Back-to-bottom catches up and resumes following future output')
            page.get_by_role('button',name='暂停展示',exact=True).click(); saved=viewport_state()
            emit(720,False);page.wait_for_timeout(150)
            check('Explicit pause freezes displayed records and position',viewport_state()==saved)
            page.get_by_role('button',name='继续展示',exact=True).click()
            expect(body).to_contain_text('LOG00720');bottom();expect(auto).to_be_checked()
            check('Continue display resumes at the newest output')
            body.focus();page.keyboard.press('PageUp');expect(auto).not_to_be_checked()
            check('PageUp pauses follow without targeting the tiny scrollbar')
            page.keyboard.press('End');bottom();expect(auto).to_be_checked()
            check('End resumes follow from the keyboard')
            auto.uncheck();saved=viewport_state();emit(800,False);page.wait_for_timeout(150)
            check('Auto-scroll switch can hold the current view',viewport_state()==saved)
            auto.check();expect(body).to_contain_text('LOG00800');bottom()
            check('Auto-scroll switch catches up immediately')
            page.get_by_label('筛选日志内容',exact=True).fill('NEEDLE')
            expect(rows.first).to_contain_text('NEEDLE');bottom();emit(880);bottom()
            check('Filtered live logs keep following the newest matching records')
            page.get_by_label('筛选日志内容',exact=True).fill('no-such-line')
            expect(rows).to_have_count(0);expect(auto).to_be_checked()
            check('Empty filter results do not accidentally disable follow')
            page.get_by_label('筛选日志内容',exact=True).fill('');bottom()
            page.set_viewport_size({'width':390,'height':844});bottom()
            check('Wrapped long logs stay at bottom after viewport resize')
            check('Mobile page has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.set_viewport_size({'width':1440,'height':1100});bottom()
            body.evaluate('(e)=>{e.scrollTop=Math.max(0,e.scrollTop-350)}');expect(auto).not_to_be_checked()
            body.evaluate('(e)=>{e.scrollTop=e.scrollHeight}');expect(auto).to_be_checked();bottom()
            check('Moving the scrollbar to bottom resumes following')
            page.get_by_role('button',name='项目管理',exact=True).click()
            emit(960,False)
            page.get_by_role('button',name='运行台',exact=True).click()
            expect(body).to_contain_text('LOG00960');bottom()
            check('Returning to the run page mounts at the newest log')
            emit(2200);bottom();expect(rows).to_have_count(120)
            check('More than 1,000 incoming records keeps DOM bounded and follow active')
            other_root=n.root/'other project';other_root.mkdir()
            other=n.project(other_root,'另一个项目')
            page.get_by_role('button',name='刷新状态',exact=True).click()
            page.get_by_label('当前项目',exact=True).select_option(other['id']);expect(rows).to_have_count(0)
            page.get_by_label('当前项目',exact=True).select_option(project['id'])
            expect(body).to_contain_text('LOG02200');bottom()
            check('Switching project resets review state and returns to its latest output')
            page.reload();expect(body).to_contain_text('LOG02200');bottom()
            check('Reloaded session snapshot also opens at bottom')
            check('No uncaught browser exceptions',not report['errors'])
            panel.screenshot(path=str(OUT/'native-log-scroll-follow.png'))
            body.hover();page.mouse.wheel(0,-400);expect(auto).not_to_be_checked()
            panel.screenshot(path=str(OUT/'native-log-scroll-review.png'))
            browser.close()
            report['backend_version']=n.api('state').get('version','0.4.2 (reused release)')
try:
    main();report['passed']=True
finally:
    (OUT/'native-log-scroll.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
