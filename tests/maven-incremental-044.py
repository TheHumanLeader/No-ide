"""Real Maven module reuse: content freshness, deletion, ABI, restart and UI.
Only synthetic code and an isolated Maven repository. Never touches user PMS.
"""
import hashlib,json,os,pathlib,shutil,socket,sys,time,urllib.request
from playwright.sync_api import sync_playwright,expect
from native_harness import Native,ROOT,wait_for
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
report={'passed':False,'checks':[],'platform':sys.platform,'errors':[],'runs':[]}
def check(name,ok=True):
 assert ok,name
 report['checks'].append(name);print('PASS',name,flush=True)
def put(p,text):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
def freeport():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def signature(p):return (p.stat().st_mtime_ns,hashlib.sha256(p.read_bytes()).hexdigest())
def response(port):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/probe',timeout=2) as r:return json.load(r)
 except (OSError,ValueError):return None
def view(n,i):return next((v for v in n.api('state')['runs'] if v['instance']==i['id']),{})
def stop(n,p,i):
 n.api('run.stop',{'project':p['id'],'instance':i['id']});wait_for(lambda:view(n,i).get('state')=='stopped',30)
def selection(n,c):
 logs=n.api('logs');items=[json.loads(l['text']) for l in logs if l['instance']==c['id'] and l['stream']=='build-selection']
 assert items,logs[-15:]
 return items[-1]
def start(n,p,i,c,label,mode,selected):
 begin=time.monotonic();n.api('run.start',{'project':p['id'],'instance':i['id']})
 def ready():
  v=view(n,i)
  if v.get('state')=='error':raise AssertionError({'state':v,'logs':n.api('logs')[-35:]})
  return response(i['port'])
 result=wait_for(ready,300);sel=selection(n,c)
 report['runs'].append({'label':label,'selection':sel,'through_http_seconds':round(time.monotonic()-begin,3),'response':result})
 check(label+' selects exactly the affected modules',sel['mode']==mode and set(sel['selected'])==set(selected))
 return result

def main():
 with Native() as n:
  root=n.root/'incremental workspace';root.mkdir();root=root.resolve()
  repo=n.root/'isolated Maven cache';repo.mkdir()
  settings=n.root/'Maven settings.xml';put(settings,'<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"/>')
  java=os.environ['TEST_JAVA8'];e=n.api('environments.save',{'kind':'java','path':java,'name':'Java 8 incremental','default':True})
  mvn=shutil.which('mvn.cmd' if os.name=='nt' else 'mvn');assert mvn
  for kind,path in [('maven',pathlib.Path(mvn).resolve()),('maven_repository',repo),('maven_settings',settings)]:n.api('build_tools.save',{'kind':kind,'path':str(path)})
  put(root/'pom.xml','''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.5.15</version><relativePath/></parent><groupId>local.incremental</groupId><artifactId>workspace</artifactId><version>1.0.0</version><packaging>pom</packaging><properties><java.version>1.8</java.version><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><modules><module>common</module><module>stable</module><module>app</module><module>unrelated</module></modules></project>''')
  parent='<modelVersion>4.0.0</modelVersion><parent><groupId>local.incremental</groupId><artifactId>workspace</artifactId><version>1.0.0</version></parent>'
  for name in ['common','stable','unrelated']:put(root/name/'pom.xml','<project>'+parent+'<artifactId>'+name+'</artifactId></project>')
  put(root/'app/pom.xml','<project>'+parent+'''<artifactId>app</artifactId><dependencies><dependency><groupId>local.incremental</groupId><artifactId>common</artifactId><version>1.0.0</version></dependency><dependency><groupId>local.incremental</groupId><artifactId>stable</artifactId><version>1.0.0</version></dependency><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-websocket</artifactId></dependency></dependencies><build><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin></plugins></build></project>''')
  put(root/'unrelated/src/main/java/Broken.java','invalid unrelated Java, never build this module')
  common=root/'common/src/main/java/fixture/shared/Value.java'
  def common_code(value):return 'package fixture.shared;public class Value {public static final String VALUE="'+value+'";}'
  put(common,common_code('one'));removed=root/'common/src/main/java/fixture/shared/Removed.java';put(removed,'package fixture.shared; public class Removed { public static class Inner {} }')
  resource=root/'common/src/main/resources/remove-me.txt';put(resource,'old resource')
  put(root/'stable/src/main/java/fixture/stable/Stable.java','package fixture.stable;public class Stable {public static String value(){return "stable";}}')
  put(root/'app/src/main/java/fixture/app/App.java','''package fixture.app;import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.context.annotation.Bean;import org.springframework.web.socket.server.standard.ServerEndpointExporter;
@SpringBootApplication public class App {@Bean public ServerEndpointExporter exporter(){return new ServerEndpointExporter();} public static void main(String[] args){SpringApplication.run(App.class,args);}}''')
  put(root/'app/src/main/java/fixture/app/Room.java','''package fixture.app;import javax.websocket.*;import javax.websocket.server.*;import org.springframework.stereotype.Component;@Component @ServerEndpoint("/ws") public class Room {@OnMessage public String receive(String text){return fixture.shared.Value.VALUE;}}''')
  probe=root/'app/src/main/java/fixture/app/Probe.java'
  def probe_code(version):return '''package fixture.app;import java.util.*;import org.springframework.web.bind.annotation.*;@RestController public class Probe {
@GetMapping("/probe") public Map<String,Object> probe(){Map<String,Object> m=new HashMap<>();m.put("app","'''+version+'''");m.put("common",fixture.shared.Value.VALUE);m.put("stable",fixture.stable.Stable.value());m.put("removed",getClass().getResource("/remove-me.txt")!=null);boolean c=false;try{Class.forName("fixture.shared.Removed$Inner");c=true;}catch(ClassNotFoundException ignored){}m.put("oldClass",c);return m;}}'''
  put(probe,probe_code('a1'))
  p=n.project(root,'增量构建实测');c=n.api('config.save',{'project':p['id'],'config':{'id':'','name':'Spring 增量测试','cwd':'app','environment_id':e['id'],'launcher':{'kind':'spring-maven','target':'pom.xml','arguments':['--server.port={port}','--server.address=127.0.0.1']},'watch':[],'env':{}}})
  i=n.api('instance.save',{'project':p['id'],'instance':{'id':'','name':'实际接口','config_id':c['id'],'port':freeport(),'args':[],'env':{}}})
  first=start(n,p,i,c,'first baseline','baseline',['.','common','stable','app']);check('Baseline actual response',first['common']=='one' and first['oldClass'] and first['removed']);stop(n,p,i)
  jar=lambda name:repo/'local/incremental'/name/'1.0.0'/(name+'-1.0.0.jar')
  stable_before=signature(jar('stable'));common_before=signature(jar('common'))
  start(n,p,i,c,'stop/start unchanged','reuse',[]);check('No-change startup does not rewrite dependency JARs',signature(jar('stable'))==stable_before and signature(jar('common'))==common_before);stop(n,p,i)
  n.stop();n.start();start(n,p,i,c,'executor restart unchanged','reuse',[]);check('Build fingerprints survive real executor exit');stop(n,p,i)
  old_time=probe.stat();put(probe,probe_code('a2'));os.utime(probe,ns=(old_time.st_atime_ns,old_time.st_mtime_ns))
  changed=start(n,p,i,c,'entry edit with original timestamp','incremental',['app']);check('Source content, not timestamp, controls freshness',changed['app']=='a2');check('Entry edit reuses upstream bytecode and JARs',signature(jar('stable'))==stable_before and signature(jar('common'))==common_before);stop(n,p,i)
  put(common,common_code('two'));changed=start(n,p,i,c,'shared constant edit','incremental',['common','app']);check('Downstream constants recompiled',changed['common']=='two');check('Unchanged sibling really untouched',signature(jar('stable'))==stable_before)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1100});page.on('pageerror',lambda e:report['errors'].append(str(e)));page.goto(n.url)
   result=page.evaluate('''port=>new Promise((resolve,reject)=>{const w=new WebSocket('ws://127.0.0.1:'+port+'/ws');const t=setTimeout(()=>{w.close();reject(Error('timeout'))},10000);w.onopen=()=>w.send('probe');w.onmessage=e=>{clearTimeout(t);resolve(e.data);w.close()};w.onerror=()=>reject(Error('ws'))})''',i['port'])
   check('Real WebSocket handler uses recompiled shared constant',result=='two')
   expect(page.get_by_role('button',name='增量构建',exact=True)).to_be_visible();expect(page.get_by_role('button',name='清理重建',exact=True)).to_be_visible();check('Normal incremental and full repair are separate controls')
   page.once('dialog',lambda d:d.dismiss());page.get_by_role('button',name='清理重建',exact=True).click();check('Declined repair leaves actual process running',view(n,i)['state']=='running')
   page.screenshot(path=str(OUT/'native-incremental-044.png'),full_page=True);browser.close()
  stop(n,p,i);removed.unlink();resource.unlink()
  changed=start(n,p,i,c,'deleted class/inner-class/resource','incremental',['common','app']);check('Deletion removes actual runtime class and resource',not changed['oldClass'] and not changed['removed']);check('Deletion does not rebuild stable dependency',signature(jar('stable'))==stable_before);stop(n,p,i)
  jar('common').write_bytes(b'not the accepted jar')
  start(n,p,i,c,'installed dependency replaced','incremental',['common','app']);check('Overwritten installed JAR restored from workspace',jar('common').read_bytes()[:2]==b'PK');stop(n,p,i)
  shutil.rmtree(root/'app/target/classes')
  start(n,p,i,c,'compiled output missing','incremental',['app']);stop(n,p,i)
  put(probe,'broken Java')
  n.api('run.start',{'project':p['id'],'instance':i['id']});wait_for(lambda:view(n,i).get('state')=='error',180)
  check('Failed compilation is not published as latest',not response(i['port']))
  stop(n,p,i);put(probe,probe_code('a3'));fixed=start(n,p,i,c,'retry incomplete build','incremental',['app']);check('Failed state remains dirty until successful rebuild',fixed['app']=='a3')
  n.api('run.repair',{'project':p['id'],'instance':i['id']},status=400);check('Full clean requires separate explicit confirmation')
  rev=view(n,i)['revision'];n.api('run.repair',{'project':p['id'],'instance':i['id'],'confirmed':True})
  wait_for(lambda:view(n,i).get('revision',0)>rev and response(i['port']),300);sel=selection(n,c)
  check('Explicit full repair includes all required modules',set(sel['selected'])=={'.','common','stable','app'} and sel['mode']=='baseline')
  stop(n,p,i)
  # A file-activated Profile changes the source root without changing the POM.
  # Cache invalidation must re-read the Maven effective model, not just compile
  # the previous graph/source folder and accidentally claim freshness.
  cpom=root/'common/pom.xml'
  original_pom=cpom.read_text(encoding='utf8')
  put(cpom,original_pom.replace('</project>', '<profiles><profile><id>alternate-source</id><activation><file><exists>${basedir}/alternate.flag</exists></file></activation><build><sourceDirectory>${project.basedir}/src/profile-on/java</sourceDirectory></build></profile></profiles></project>'))
  alt=root/'common/src/profile-on/java/fixture/shared/Value.java';put(alt,common_code('profile-source'))
  start(n,p,i,c,'POM edit revalidates model','baseline',['.','common','stable','app']);stop(n,p,i)
  flag=root/'common/alternate.flag';put(flag,'')
  profile=start(n,p,i,c,'file Profile activated','baseline',['.','common','stable','app'])
  check('File activation switches actual source root',profile['common']=='profile-source');stop(n,p,i)
  flag.unlink()
  profile=start(n,p,i,c,'file Profile deactivated','baseline',['.','common','stable','app'])
  check('Removing Profile marker restores original source model',profile['common']=='two')
  check('No unrelated module built',not(root/'unrelated/target/classes').exists())
  check('No uncaught browser errors',not report['errors'])
  report['health']=json.load(urllib.request.urlopen(n.base+'/api/health'))
try:main();report['passed']=True
except Exception as e:report['failure']=str(e);raise
finally:(OUT/'native-incremental-044.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
