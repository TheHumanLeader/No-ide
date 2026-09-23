"""Real native task state, cancellation, restart readiness and production UI.
Temporary Python build/app fixture only; no mock APIs or user project data.
"""
import json, pathlib, shutil, sys, time, urllib.request
from playwright.sync_api import sync_playwright, expect
from native_harness import Native, ROOT, wait_for
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
report={'passed':False,'checks':[],'errors':[],'platform':sys.platform}
def check(name,value=True):
 assert value,name
 report['checks'].append(name);print('PASS',name,flush=True)
def main():
 with Native() as n:
  root=n.root/'feedback fixture';root.mkdir()
  settings=root/'build-settings.json'
  def mode(wait=0,fail=False,version='v1',delay=0):settings.write_text(json.dumps(dict(wait=wait,fail=fail,version=version,delay=delay)),encoding='utf8')
  mode()
  (root/'build.py').write_text('''import json,os,pathlib,time,sys
s=json.loads(pathlib.Path('build-settings.json').read_text())
pathlib.Path('builder.pid').write_text(str(os.getpid()))
print('ACTUAL BUILD START',flush=True)
time.sleep(s['wait'])
if s['fail']:print('deliberate compile failure',flush=True);sys.exit(3)
pathlib.Path('compiled.json').write_text(json.dumps(s))
print('ACTUAL BUILD END',flush=True)
''',encoding='utf8')
  (root/'app.py').write_text('''import http.server,json,pathlib,os,time
s=json.loads(pathlib.Path('compiled.json').read_text())
time.sleep(s['delay'])
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'version':s['version'],'pid':os.getpid()}).encode())
http.server.HTTPServer(('127.0.0.1',int(os.environ['PORT'])),Handler).serve_forever()
''',encoding='utf8')
  import socket
  def port():
   with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
  p=n.project(root,'构建反馈验收')
  c=n.api('config.save',{'project':p['id'],'config':{'id':'','name':'Python 构建配置','cwd':'.','command':{'program':sys.executable,'args':['-u','app.py']},'build':{'program':sys.executable,'args':['-u','build.py']},'watch':[],'env':{}}})
  instances=[n.api('instance.save',{'project':p['id'],'instance':{'id':'','name':name,'config_id':c['id'],'port':port(),'args':[],'env':{}}}) for name in ['主实例','同配置副本']]
  def params(i=instances[0]):return {'project':p['id'],'instance':i['id']}
  def view(i=instances[0]):return next((v for v in n.api('state')['runs'] if v['instance']==i['id']),{})
  def task():return next((t for t in n.api('state').get('activities',[]) if t['config']==c['id']),{})
  def result(i=instances[0]):return json.load(urllib.request.urlopen('http://127.0.0.1:'+str(i['port']),timeout=2))
  for i in instances:
   n.api('run.start',params(i));wait_for(lambda:view(i).get('state')=='running',30)
  before=[result(i) for i in instances]
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1440,'height':1100});page.set_default_timeout(10000)
   page.on('pageerror',lambda e:report['errors'].append(str(e)));page.goto(n.url)
   row=page.locator('.live-instance').filter(has=page.locator('.live-instance-main>strong',has_text='主实例'))
   card=row.locator('.build-activity')
   expect(row.get_by_role('button',name='应用改动',exact=True)).to_be_enabled()
   mode(wait=60,version='v2');row.get_by_role('button',name='应用改动',exact=True).click()
   expect(card).to_be_visible();wait_for(lambda:task().get('phase')=='building')
   expect(card).to_contain_text('正在执行构建');expect(row.locator('.task-apply')).to_be_disabled()
   check('Click immediately shows real task phase and disables duplicate apply')
   check('Shared configuration lists both affected instances',len(task()['instances'])==2)
   n.api('run.apply',params(),status=400);check('Repeated API request cannot queue another build')
   page.get_by_role('button',name='暂停日志显示',exact=True).click()
   expect(page.locator('.live-log-pause-note')).to_contain_text('构建、任务进度和实例仍继续运行')
   check('Log pause explicitly does not pause the build',task()['phase']=='building')
   duration=card.locator('.task-duration').inner_text();page.wait_for_timeout(1200)
   check('Elapsed duration progresses even with logs paused',card.locator('.task-duration').inner_text()!=duration)
   page.reload();expect(card).to_contain_text('正在执行构建')
   check('Reload restores active task from backend snapshot')
   card.screenshot(path=str(OUT/'native-feedback-051-building.png'))
   task_id=task()['id'];card.get_by_role('button',name='取消本次构建',exact=True).click()
   wait_for(lambda:task().get('status')=='cancelled');expect(card).to_contain_text('本次构建已取消')
   time.sleep(.5)
   check('Cancel stops only build; both original process IDs and responses survive',[result(i) for i in instances]==before)
   check('Cancelled task has authoritative end time',task()['finished_at'] is not None)
   mode(wait=.5,version='v2',delay=2)
   row.get_by_role('button',name='应用改动',exact=True).click();wait_for(lambda:task().get('phase')=='waiting',30)
   expect(card).to_contain_text('等待就绪');check('Build completion is not announced as ready while app is starting',task()['status']=='running')
   n.api('run.cancel',{**params(),'task_id':task_id},status=400);check('Stale cancellation does not cancel a later task')
   wait_for(lambda:task().get('status')=='succeeded',30);expect(card).to_contain_text('更新完成')
   check('Success is backed by new process and actual HTTP content',all(result(i)['version']=='v2' for i in instances))
   page.reload();expect(card).to_contain_text('更新完成');check('Completion survives page reload and does not disappear')
   card.screenshot(path=str(OUT/'native-feedback-051-completed.png'))
   before=[result(i) for i in instances]
   mode(wait=.3,fail=True,version='v3');row.get_by_role('button',name='应用改动',exact=True).click()
   wait_for(lambda:task().get('status')=='failed',30);expect(card).to_contain_text('改动尚未生效')
   check('Failure is persistent and preserves original instances',[result(i) for i in instances]==before)
   card.locator('summary').click();expect(card).to_contain_text('deliberate compile failure')
   check('Failure details available without finding scattered logs')
   card.screenshot(path=str(OUT/'native-feedback-051-failed.png'))
   mode(wait=60,version='v4');row.get_by_role('button',name='应用改动',exact=True).click();wait_for(lambda:task().get('phase')=='building')
   row.get_by_role('button',name='停止实例',exact=True).click();wait_for(lambda:view().get('state')=='stopped',30)
   check('Stop instance also cancels shared build without stopping its sibling',task()['status']=='cancelled' and result(instances[1])==before[1])
   page.set_viewport_size({'width':390,'height':844});check('Progress UI does not overflow mobile viewport',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
   check('No uncaught browser errors',not report['errors'])
   report['version']=json.load(urllib.request.urlopen(n.base+'/health'))['version']
   browser.close()
try:
 main();report['passed']=True
finally:(OUT/'native-feedback-051.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
