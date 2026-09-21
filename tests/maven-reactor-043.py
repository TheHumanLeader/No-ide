"""Actual stale local JAR + deleted class/resource + WebSocket regression.
Uses only a disposable Maven repository and synthetic fixture code. No user code.
"""
import hashlib,json,os,pathlib,shutil,socket,subprocess,sys,time,urllib.request,zipfile
from native_harness import Native,ROOT,wait_for
from playwright.sync_api import sync_playwright,expect
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
report={'passed':False,'checks':[],'platform':sys.platform,'errors':[]}
def check(name,ok=True):
 assert ok,name
 report['checks'].append(name);print('PASS',name,flush=True)
def put(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf8')
def freeport():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def response(port):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/probe',timeout=2) as r:return json.load(r)
 except (OSError,ValueError):return None
def view(n,i):return next((v for v in n.api('state')['runs'] if v['instance']==i['id']),{})
def start(n,p,i):
 n.api('run.start',{'project':p['id'],'instance':i['id']})
 def ready():
  v=view(n,i)
  if v.get('state')=='error':raise AssertionError({'state':v,'logs':n.api('logs')[-20:]})
  return response(i['port'])
 return wait_for(ready,180)
def stop(n,p,i):
 n.api('run.stop',{'project':p['id'],'instance':i['id']});wait_for(lambda:view(n,i).get('state')=='stopped',30)
def run_mvn(exe,args,cwd,java):
 r=subprocess.run([str(exe),*map(str,args)],cwd=cwd,env={**os.environ,'JAVA_HOME':java},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600,shell=os.name=='nt')
 assert r.returncode==0,r.stdout[-6000:].decode(errors='replace')
 return r.stdout

def main():
 with Native() as n:
  root=n.root/'workspace with spaces';root.mkdir();core=root/'common';app=root/'app'
  cache=n.root/'isolated local repository';cache.mkdir();setting=n.root/'Maven settings.xml'
  put(setting,'<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"/>')
  java=os.environ['TEST_JAVA8'];e=n.api('environments.save',{'kind':'java','path':java,'name':'Java 8 reactor test','default':True})
  mvn=shutil.which('mvn.cmd' if os.name=='nt' else 'mvn');assert mvn
  n.api('build_tools.save',{'kind':'maven','path':str(pathlib.Path(mvn).resolve())})
  for kind,path in [('maven_repository',cache),('maven_settings',setting)]:n.api('build_tools.save',{'kind':kind,'path':str(path)})
  put(root/'pom.xml','''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.5.15</version><relativePath/></parent><groupId>local.fixture</groupId><artifactId>workspace</artifactId><version>1.0.0</version><packaging>pom</packaging><properties><java.version>1.8</java.version><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><modules><module>app</module><module>common</module><module>unrelated</module></modules></project>''')
  child='<modelVersion>4.0.0</modelVersion><parent><groupId>local.fixture</groupId><artifactId>workspace</artifactId><version>1.0.0</version></parent>'
  put(core/'pom.xml','<project>'+child+'<artifactId>common</artifactId><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-websocket</artifactId></dependency></dependencies></project>')
  put(app/'pom.xml','<project>'+child+'''<artifactId>app</artifactId><dependencies><dependency><groupId>local.fixture</groupId><artifactId>common</artifactId><version>1.0.0</version></dependency></dependencies><build><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin></plugins></build></project>''')
  put(root/'unrelated/pom.xml','<project>'+child+'<artifactId>unrelated</artifactId></project>')
  put(root/'unrelated/src/main/java/Broken.java','intentionally invalid unrelated source')
  appcode='''package fixture.app;
import java.util.*;import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.context.annotation.*;import org.springframework.web.socket.server.standard.ServerEndpointExporter;
@SpringBootApplication(scanBasePackages="fixture") public class App {
@Bean public ServerEndpointExporter exporter(){return new ServerEndpointExporter();}
public static void main(String[] a){SpringApplication.run(App.class,a);}}
'''
  put(app/'src/main/java/fixture/app/App.java',appcode)
  api='''package fixture.shared;
import java.util.*;import org.springframework.web.bind.annotation.*;
@RestController public class Probe {
@GetMapping("/probe") public Map<String,Object> probe(){Map<String,Object> m=new LinkedHashMap<>();m.put("version",Commands.version());m.put("source",Commands.class.getProtectionDomain().getCodeSource().getLocation().toString());m.put("cwd",System.getProperty("user.dir"));
boolean old=false;try{Class.forName("fixture.shared.RemovedLogger");old=true;}catch(ClassNotFoundException ignored){}m.put("oldClass",old);m.put("oldResource",getClass().getResource("/removed-logger.xml")!=null);m.put("oldAppResource",getClass().getResource("/removed-entry.properties")!=null);return m;}}
'''
  put(core/'src/main/java/fixture/shared/Probe.java',api)
  put(core/'src/main/java/fixture/shared/Room.java','''package fixture.shared;
import javax.websocket.*;import javax.websocket.server.*;import org.springframework.stereotype.Component;
@Component @ServerEndpoint("/ws") public class Room {
@OnMessage public String receive(String command){return Commands.execute(command);}}
''')
  def command(version,reply):put(core/'src/main/java/fixture/shared/Commands.java',f'''package fixture.shared;public class Commands {{public static String version(){{return "{version}";}}public static String execute(String command){{return "{reply}";}}}}''')
  command('old-installed-jar','UNREGISTERED')
  removed=core/'src/main/java/fixture/shared/RemovedLogger.java';put(removed,'package fixture.shared;public class RemovedLogger {}')
  removed_resource=core/'src/main/resources/removed-logger.xml';put(removed_resource,'old logger configuration')
  removed_app=app/'src/main/resources/removed-entry.properties';put(removed_app,'old.entry=true')
  opts=['--batch-mode','--no-transfer-progress','--settings',str(setting),f'-Dmaven.repo.local={cache}']
  run_mvn(mvn,[*opts,'-pl','app','-am','-DskipTests','install'],root,java)
  jar=cache/'local/fixture/common/1.0.0/common-1.0.0.jar';oldhash=hashlib.sha256(jar.read_bytes()).hexdigest()
  check('Preinstalled genuine old release JAR contains deleted class','fixture/shared/RemovedLogger.class' in zipfile.ZipFile(jar).namelist())
  removed.unlink();removed_resource.unlink();removed_app.unlink();command('current-workspace-source','JOINED')
  check('Old target/classes still contains removed bytecode before repair',(core/'target/classes/fixture/shared/RemovedLogger.class').is_file())
  originals={x:hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob('*') if x.is_file() and 'target' not in x.parts}
  p=n.project(root,'Multi module regression')
  # Reproduce v0.4.2 using a raw per-module launch, not mock logs.
  oldcfg=n.api('config.save',{'project':p['id'],'config':{'id':'','name':'old-single-module','cwd':'app','build':{'program':str(mvn),'args':[*opts,'compile']},'command':{'program':str(mvn),'args':[*opts,'spring-boot:run','-Dspring-boot.run.arguments=--server.port={port} --server.address=127.0.0.1']},'env':{'JAVA_HOME':java},'watch':[]}})
  old=n.api('instance.save',{'project':p['id'],'instance':{'id':'','name':'old baseline','config_id':oldcfg['id'],'port':freeport(),'args':[],'env':{}}})
  baseline=start(n,p,old);report['before']=baseline
  check('Old per-module launch demonstrably loads stale dependency',baseline['version']=='old-installed-jar' and baseline['oldClass'] and baseline['oldResource'])
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1150});page.set_default_timeout(30000);page.on('pageerror',lambda x:report['errors'].append(str(x)));page.goto(n.url)
   def ws(port):return page.evaluate('''port=>new Promise((resolve,reject)=>{const w=new WebSocket('ws://127.0.0.1:'+port+'/ws');const t=setTimeout(()=>{w.close();reject(Error('WS timeout'))},10000);w.onopen=()=>w.send('ws.room.createAndJoin');w.onmessage=e=>{clearTimeout(t);resolve(e.data);w.close()};w.onerror=()=>{clearTimeout(t);reject(Error('WS error'))}})''',port)
   check('Real baseline WebSocket dispatch reproduces unregistered command',ws(old['port'])=='UNREGISTERED')
   stop(n,p,old)
   cfg=n.api('config.save',{'project':p['id'],'config':{'id':'','name':'workspace launcher','cwd':'app','environment_id':e['id'],'launcher':{'kind':'spring-maven','target':'pom.xml','arguments':['--server.port={port}','--server.address=127.0.0.1']},'env':{},'watch':[]}})
   preview=n.api('launch.preview',{'project':p['id'],'config':cfg});report['preview']=preview
   check('Automatically finds root POM and separates module from application cwd',preview['maven']['root']=='.' and preview['maven']['module']=='app' and preview['cwd']=='.')
   check('Build selects entry plus dependencies and clears old outputs','--also-make' in preview['build']['args'] and 'clean' in preview['build']['args'] and 'install' in preview['build']['args'])
   check('Run selects only the app, not all reactor modules','--also-make' not in preview['command']['args'] and '-pl' in preview['command']['args'])
   i=n.api('instance.save',{'project':p['id'],'instance':{'id':'','name':'current workspace','config_id':cfg['id'],'port':freeport(),'args':[],'env':{}}})
   current=start(n,p,i);report['after']=current
   check('Actual Spring Boot process loads current workspace dependency',current['version']=='current-workspace-source')
   check('Removed class and resources are absent from actual classpath',not current['oldClass'] and not current['oldResource'] and not current['oldAppResource'])
   check('Actual business WebSocket command dispatch is updated',ws(i['port'])=='JOINED')
   check('Runtime directory is reactor root, not entry module',pathlib.Path(current['cwd']).samefile(root))
   check('Local dependency JAR really changed, not just a banner',oldhash!=hashlib.sha256(jar.read_bytes()).hexdigest())
   check('Unrelated broken module is not compiled',not(root/'unrelated/target/classes').exists())
   page.get_by_role('button',name='刷新状态',exact=True).click();page.locator('.run-config-card',has_text='workspace launcher').get_by_role('button',name='编辑配置',exact=True).click()
   expect(page.get_by_label('Maven 聚合目录',exact=True)).to_be_visible();expect(page.get_by_label('应用工作目录',exact=True)).to_be_visible()
   page.get_by_role('button',name='查看构建范围与启动目录',exact=True).click();expect(page.get_by_test_id('maven-plan')).to_contain_text('入口 + Maven 判定的依赖模块')
   page.screenshot(path=str(OUT/'native-reactor-043-config.png'),full_page=True);page.get_by_role('button',name='取消',exact=True).click()
   check('Visual configuration exposes reactor and runtime directory without typing paths')
   stop(n,p,i)
   # Subsequent process startup must not retain the installed previous release.
   command('second-source-edit','JOINED_V2');again=start(n,p,i)
   check('Restart uses another source edit of same artifact version',again['version']=='second-source-edit' and ws(i['port'])=='JOINED_V2')
   stop(n,p,i)
   # Active watcher also sees sibling modules, not only app/src.
   cfg['watch']=['app/src'];cfg=n.api('config.save',{'project':p['id'],'config':cfg});start(n,p,i)
   command('sibling-watcher-edit','JOINED_V3')
   wait_for(lambda:(response(i['port']) or {}).get('version')=='sibling-watcher-edit',180)
   check('Editing dependency module automatically rebuilds despite entry-only watch setting',ws(i['port'])=='JOINED_V3')
   stop(n,p,i)
   # Custom app directory uses selector-relative path; profiles are separately persisted.
   cfg['launcher']['working_directory']='app';cfg['launcher']['maven_profiles']=[];cfg['launcher']['maven_properties']={'fixture.value':'value with spaces'}
   n.api('config.save',{'project':p['id'],'config':cfg});custom=start(n,p,i)
   check('Explicit application cwd overrides root without changing module selection',pathlib.Path(custom['cwd']).samefile(app));stop(n,p,i)
   cfg['launcher']['maven_root']='../outside';n.api('config.save',{'project':p['id'],'config':cfg},status=400)
   check('Outside-root reactor path is rejected')
   check('Build did not rewrite POMs or other source files',all(x.name=='Commands.java' or hashlib.sha256(x.read_bytes()).hexdigest()==h for x,h in originals.items()))
   check('No uncaught browser errors',not report['errors']);browser.close()
try:main();report['passed']=True
except Exception as e:report['failure']=str(e);raise
finally:(OUT/'native-reactor-043.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
