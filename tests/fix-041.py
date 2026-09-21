"""Real Windows/Linux regressions: 150-file batch grouping and Maven Spring startup.
All files and repositories are disposable. No user repositories or credentials are used.
"""
import copy, json, os, pathlib, platform, shutil, socket, subprocess, time, urllib.request
from native_harness import Native, ROOT, cli, wait_for
from playwright.sync_api import sync_playwright, expect
checks=[];timings={};details={};OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
def check(name,condition=True):
 assert condition,name
 checks.append(name);print('PASS',name,flush=True)
def browser(pw):return pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
def groups_test():
 with Native() as n:
  clients=n.api('tools.detect');git=clients['git']['selected']['path'];svn=clients['svn']['selected']['path']
  for kind,exe in [('git',git),('svn',svn)]:
   wc=n.root/(kind+' work');wc.mkdir();server=None
   if kind=='git':
    cli(exe,'init','-b','main',cwd=wc);cli(exe,'config','user.name','Local test',cwd=wc);cli(exe,'config','user.email','test@example.invalid',cwd=wc)
   else:
    admin=pathlib.Path(exe).with_name('svnadmin.exe' if os.name=='nt' else 'svnadmin');admin=admin if admin.is_file() else shutil.which('svnadmin');assert admin
    server=n.root/'svn server';cli(admin,'create',server);cli(exe,'checkout',server.as_uri(),wc,'--non-interactive')
   names=[f'file-{i:03}.txt' for i in range(150)]
   for name in names:(wc/name).write_text('old\n',encoding='utf8')
   if kind=='git':cli(exe,'add','.',cwd=wc);cli(exe,'commit','-m','initial',cwd=wc)
   else:cli(exe,'add',*names,cwd=wc);cli(exe,'commit','-m','initial','--non-interactive',cwd=wc)
   for name in names:(wc/name).write_text('new\n',encoding='utf8')
   p=n.project(wc,kind+' 150项批量验收');common={'project':p['id'],'repo':p['repos'][0]['id']}
   n.api('vcs.status',common);g=n.api('vcs.group.save',{**common,'name':'忽略不提交'})['items'][-1]
   with sync_playwright() as pw:
    b=browser(pw);page=b.new_page(viewport={'width':1480,'height':1080});page.set_default_timeout(30000);errors=[];calls=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def record(r):
     if r.url.endswith('/api/call'):
      try:calls.append(r.post_data_json['action'])
      except Exception:pass
    page.on('request',record);page.goto(n.url);page.get_by_label('当前项目').select_option(p['id']);page.locator('.nav-item').filter(has_text='代码管理').click()
    expect(page.locator('.live-file')).to_have_count(150)
    first=page.locator('.live-file').first;last=page.locator('.live-file').last
    first.locator('.file-row-label').click();expect(first.get_by_role('checkbox')).to_be_checked();expect(first).to_have_class('live-file active');check(kind+' row click selects checkbox and active style')
    last.locator('.file-row-label').click(modifiers=['Shift']);expect(page.locator('.live-file input:checked')).to_have_count(150);check(kind+' Shift range selects 150 rows')
    page.get_by_role('button',name='清空',exact=True).click();expect(page.locator('.live-file input:checked')).to_have_count(0)
    page.get_by_role('button',name='全选',exact=True).click();expect(page.locator('.live-file input:checked')).to_have_count(150);check(kind+' one-click select all works')
    page.get_by_label('移动到分组').select_option(g['id']);calls.clear();t=time.monotonic()
    page.get_by_role('button',name='移动选中文件',exact=True).click();expect(page.locator('.live-file')).to_have_count(0)
    timings[kind+'_browser_move_150_ms']=round((time.monotonic()-t)*1000,2)
    check(kind+' batch move sends one write without a state/status refresh',calls.count('vcs.group.move')==1 and 'vcs.status' not in calls and 'state' not in calls)
    page.get_by_role('button',name='分组 忽略不提交',exact=True).click();expect(page.locator('.live-file')).to_have_count(150)
    page.get_by_label('筛选变更文件').fill('file-00');expect(page.locator('.live-file')).to_have_count(10)
    page.get_by_role('button',name='全选筛选结果',exact=True).click();expect(page.locator('.live-file input:checked')).to_have_count(10);check(kind+' directory/name filter supports batch selection')
    page.get_by_label('筛选变更文件').fill('');page.locator('.live-files').focus();page.keyboard.press('Control+a');expect(page.locator('.live-file input:checked')).to_have_count(150)
    check(kind+' keyboard select all works')
    page.locator('.vcs-extra summary').click()
    wording='暂存选中文件（不提交）' if kind=='git' else '纳入版本控制（不提交）'
    expect(page.get_by_role('button',name=wording,exact=True)).to_be_visible();check(kind+' add/stage is explicitly not called commit')
    page.screenshot(path=str(OUT/f'native-041-{kind}-bulk.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844});check(kind+' batch toolbar fits phone viewport',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    check(kind+' no uncaught page error',not errors);b.close()
   status=n.api('vcs.status',common);check(kind+' all 150 assignments persisted',len(status['files'])==150 and all(f['group']==g['id'] for f in status['files']))
   n.stop();config=n.root/'data/settings.json';data=json.loads(config.read_text(encoding='utf8'));old=data['tools'].get(kind);data['tools'][kind]=str(n.root/'missing-client');config.write_text(json.dumps(data),encoding='utf8');n.start()
   t=time.monotonic();n.api('vcs.group.move',{**common,'group':'default','paths':names});timings[kind+'_metadata_move_150_ms']=round((time.monotonic()-t)*1000,2)
   check(kind+' batch grouping works with client unavailable: metadata only')
   n.api('vcs.group.move',{**common,'group':g['id'],'paths':names});n.stop();data=json.loads(config.read_text(encoding='utf8'));data['tools'][kind]=old;config.write_text(json.dumps(data),encoding='utf8');n.start()
   status=n.api('vcs.status',common);check(kind+' grouping survives process restart',all(f['group']==g['id'] for f in status['files']))
   check(kind+' grouping has not committed file contents',(cli(exe,'show','HEAD:'+names[0],cwd=wc) if kind=='git' else cli(exe,'cat',server.as_uri()+'/'+names[0]))=='old')
   n.api('vcs.group.move',{**common,'group':'default','paths':['../escape']},status=400);check(kind+' batch API rejects path traversal')

def maven_test():
 with Native() as n:
  java=os.environ['TEST_JAVA8'];env=n.api('environments.save',{'kind':'java','path':java,'name':'Java 8 验证','default':True});check('Java8 selected for actual Maven test',env['major']==8)
  mvn=shutil.which('mvn.cmd' if os.name=='nt' else 'mvn');assert mvn,'Maven must exist in the CI test environment'
  home=pathlib.Path(mvn).resolve().parent.parent;installed=n.root/'Maven tools with spaces';shutil.copytree(home,installed)
  exe=installed/'bin'/('mvn.cmd' if os.name=='nt' else 'mvn')
  n.api('build_tools.save',{'kind':'maven','path':str(installed)})
  report=n.api('build_tools.detect')['maven'];details['maven_detection']=report
  actual_program=pathlib.Path(report['selected']['path'])
  # Windows TEMP may contain RUNNER~1; compare file identity, not 8.3 spelling.
  check('Maven folder resolved and version verified',report['version'].startswith('Apache Maven ') and actual_program.samefile(exe))
  exe=actual_program
  root=n.root/'Spring test project';module=root/'modules/admin';module.mkdir(parents=True)
  (module/'pom.xml').write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.18</version><relativePath/></parent><groupId>local.noide</groupId><artifactId>launch-test</artifactId><version>1.0</version><properties><java.version>1.8</java.version><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency></dependencies><build><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin></plugins></build></project>''',encoding='utf8')
  src=module/'src/main/java/fixture/App.java';src.parent.mkdir(parents=True);src.write_text('''package fixture;
import java.util.*;import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.web.bind.annotation.*;import org.springframework.beans.factory.annotation.Value;
@SpringBootApplication @RestController public class App {
@Value("${probe.argument:unset}") String argument;
@GetMapping("/probe") public Map<String,String> probe(){Map<String,String> m=new LinkedHashMap<>();m.put("java",System.getProperty("java.version"));m.put("property",System.getProperty("probe.property"));m.put("argument",argument);m.put("env",System.getenv("NO_IDE_PROBE"));return m;}
public static void main(String[] a){SpringApplication.run(App.class,a);}}''',encoding='utf8')
  settings=n.root/'maven settings.xml';settings.write_text('<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"/>',encoding='utf8');cache=n.root/'maven repository';cache.mkdir()
  n.api('build_tools.save',{'kind':'maven_settings','path':str(settings)});n.api('build_tools.save',{'kind':'maven_repository','path':str(cache)})
  args=[str(exe),'--batch-mode','--no-transfer-progress','--settings',str(settings),f'-Dmaven.repo.local={cache}','-DskipTests','package','spring-boot:help'];log=OUT/'native-041-maven-warmup.log'
  with log.open('wb') as out:result=subprocess.run(args,cwd=module,env={**os.environ,'JAVA_HOME':java},stdout=out,stderr=subprocess.STDOUT,timeout=300,shell=os.name=='nt')
  assert result.returncode==0,log.read_text(errors='replace')[-5000:]
  p=n.project(root,'Spring 启动验收');pid=p['id'];entry=next(e for e in n.api('project.discover',{'project':pid})['entries'] if e['kind']=='spring-maven')
  c=n.api('config.save',{'project':pid,'config':{'id':'','name':'业务服务 · Spring Boot','cwd':entry['cwd'],'environment_id':env['id'],'command':{'program':'auto','args':[]},'watch':[],'env':{'NO_IDE_PROBE':'env with spaces'},'launcher':{'kind':'spring-maven','target':entry['target'],'arguments':['--server.address=127.0.0.1','--server.port={port}','--probe.argument=argument with spaces'],'properties':{'probe.property':'property with spaces'}}}})
  preview=n.api('launch.preview',{'project':pid,'config':c});check('Maven absolute path resolves for both build and run',pathlib.Path(preview['build']['program'])==exe and pathlib.Path(preview['command']['program'])==exe)
  check('Maven settings and repository are passed to both phases',all('--settings' in x['args'] and any(a.startswith('-Dmaven.repo.local=') for a in x['args']) for x in [preview['build'],preview['command']]))
  bad=copy.deepcopy(c);bad['launcher']['build_tool_path']=str(n.root/'missing-maven');err=n.api('launch.preview',{'project':pid,'config':bad},status=400)['error'];check('Missing Maven produces actionable error without fallback','maven' in err.lower() and 'program not found' not in err)
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  i=n.api('instance.save',{'project':pid,'instance':{'id':'','name':'真实 Spring 实例','config_id':c['id'],'environment_id':env['id'],'port':port,'args':[],'env':{}}})
  def start():
   n.api('run.start',{'project':pid,'instance':i['id']})
   def response():
    state=next((x for x in n.api('state')['runs'] if x['instance']==i['id']),{})
    if state.get('state')=='error':raise AssertionError({'state':state,'logs':n.api('logs')[-20:]})
    try:
     with urllib.request.urlopen(f'http://127.0.0.1:{port}/probe',timeout=1) as r:return json.load(r)
    except (OSError,ValueError):return False
   return wait_for(response,100)
  actual=start();details['spring_first_response']=actual;check('Real Spring Boot runs with selected Java and intact arguments',actual['java'].startswith('1.8.') and actual['property']=='property with spaces' and actual['argument']=='argument with spaces' and actual['env']=='env with spaces')
  n.api('run.stop',{'project':pid,'instance':i['id']});wait_for(lambda:next(s for s in n.api('state')['runs'] if s['instance']==i['id'])['state']=='stopped')
  with sync_playwright() as pw:
   b=browser(pw);page=b.new_page(viewport={'width':1440,'height':1100});page.set_default_timeout(30000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(n.url)
   card=page.locator('.run-config-card');expect(card).to_have_count(1);expect(card).to_contain_text('Java 8');check('Existing configuration shown on run page with runtime and instance')
   page.screenshot(path=str(OUT/'native-041-config-list.png'),full_page=True)
   card.get_by_role('button',name='编辑配置',exact=True).click();page.get_by_role('button',name='检查启动条件',exact=True).click();expect(page.locator('.launch-check-success')).to_contain_text('mvn');check('Editor checks resolved Maven program')
   page.get_by_label('配置名称',exact=True).fill('已修改的 Spring 配置');page.locator('.visual-advanced summary').click();page.get_by_label('系统属性值 1',exact=True).fill('changed in UI')
   page.screenshot(path=str(OUT/'native-041-config-edit.png'),full_page=True)
   page.get_by_role('button',name='保存配置',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
   saved=n.api('state')['store']['projects'][0];check('Editing preserves configuration id and instance reference',len(saved['configs'])==1 and saved['configs'][0]['id']==c['id'] and saved['instances'][0]['config_id']==c['id'])
   page.get_by_role('button',name='编辑实例配置 真实 Spring 实例',exact=True).click();expect(page.get_by_label('配置名称',exact=True)).to_have_value('已修改的 Spring 配置');page.get_by_role('button',name='取消',exact=True).click();check('Instance links to shared configuration editor')
   page.locator('.nav-item').filter(has_text='运行环境').click();expect(page.get_by_label('maven构建工具')).to_have_value(str(exe));check('Maven settings and directory choices displayed')
   page.screenshot(path=str(OUT/'native-041-build-tools.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844});check('Runtime settings have no page overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'));check('Maven/config UI has no uncaught error',not errors);b.close()
  actual=start();details['spring_edited_response']=actual;check('Edited property used by actual restarted process',actual['property']=='changed in UI')
  n.api('run.stop',{'project':pid,'instance':i['id']});wait_for(lambda:next(s for s in n.api('state')['runs'] if s['instance']==i['id'])['state']=='stopped')
  n.stop();n.start();check('Maven choices persist across executor restart',pathlib.Path(n.api('state')['store']['build_tools']['maven'])==exe)

if __name__=='__main__':
 report={'platform':platform.platform(),'checks':checks,'timings_ms':timings,'details':details,'passed':False,'scope':'Disposable repositories and Spring Boot 2.7.18; real API and Chromium. Native file dialogs not automated.'}
 try:groups_test();maven_test();report['passed']=True
 except Exception as e:report['error']=str(e);raise
 finally:(OUT/'native-fix-041.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
