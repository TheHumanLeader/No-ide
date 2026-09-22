"""Real Maven/Java8 + Java17/HTTP/WebSocket HotSwap, not a simulated agent.
Synthetic project and disposable settings only. No user files or services.
"""
import hashlib, json, os, pathlib, shutil, socket, struct, sys, time, urllib.request
from playwright.sync_api import sync_playwright, expect
from native_harness import Native, ROOT, wait_for
OUT=ROOT/'test-results'; OUT.mkdir(exist_ok=True)
report={'passed':False,'checks':[],'platform':sys.platform,'errors':[],'timings':{}}
def check(name,ok=True):
 assert ok,name
 report['checks'].append(name);print('PASS',name,flush=True)
def put(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf8')
def freeport():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def view(n,i):return next((v for v in n.api('state')['runs'] if v['instance']==i['id']),{})
def response(i):
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{i["port"]}/probe',timeout=2) as r:return json.load(r)
 except (OSError,ValueError):return None
def start(n,p,i):
 n.api('run.start',{'project':p['id'],'instance':i['id']})
 def ready():
  v=view(n,i)
  if v.get('state')=='error':raise AssertionError({'view':v,'logs':n.api('logs')[-40:]})
  return response(i)
 return wait_for(ready,300)
def stop(n,p,i):n.api('run.stop',{'project':p['id'],'instance':i['id']});wait_for(lambda:view(n,i).get('state')=='stopped',30)
def wait_update(n,i,condition):
 def done():
  v=view(n,i)
  if v.get('state')=='error' or v.get('error'):raise AssertionError({'view':v,'logs':n.api('logs')[-40:]})
  return condition(v)
 return wait_for(done,240)
def apply(n,p,i):n.api('run.apply',{'project':p['id'],'instance':i['id']})
def restart(n,p,i):
 old=(response(i) or {}).get('pid');n.api('run.restart',{'project':p['id'],'instance':i['id']})
 return wait_update(n,i,lambda v:(r:=response(i)) and r['pid']!=old and r)
def signature(p):return (p.stat().st_mtime_ns,hashlib.sha256(p.read_bytes()).hexdigest())
def selections(n,c):return [json.loads(x['text']) for x in n.api('logs') if x['instance']==c['id'] and x['stream']=='build-selection']
def main():
 with Native() as n:
  root=(n.root/'hot workspace with spaces');root.mkdir();root=root.resolve()
  repo=n.root/'isolated repo';repo.mkdir();settings=n.root/'settings.xml';put(settings,'<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"/>')
  java=n.api('environments.save',{'kind':'java','path':os.environ['TEST_JAVA8'],'name':'Java8 hot test','default':True})
  java17=n.api('environments.save',{'kind':'java','path':os.environ['TEST_JAVA17'],'name':'Java17 hot test'})
  mvn=pathlib.Path(shutil.which('mvn.cmd' if os.name=='nt' else 'mvn')).resolve()
  for kind,path in [('maven',mvn),('maven_repository',repo),('maven_settings',settings)]:n.api('build_tools.save',{'kind':kind,'path':str(path)})
  put(root/'pom.xml','''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.5.15</version><relativePath/></parent><groupId>local.hot</groupId><artifactId>workspace</artifactId><version>1.0.0</version><packaging>pom</packaging><properties><java.version>1.8</java.version><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><modules><module>common</module><module>stable</module><module>app</module><module>unrelated</module></modules></project>''')
  parent='<modelVersion>4.0.0</modelVersion><parent><groupId>local.hot</groupId><artifactId>workspace</artifactId><version>1.0.0</version></parent>'
  for name in ['common','stable','unrelated']:put(root/name/'pom.xml','<project>'+parent+'<artifactId>'+name+'</artifactId></project>')
  put(root/'unrelated/src/main/java/Broken.java','invalid unrelated module')
  put(root/'stable/src/main/java/fixture/Stable.java','package fixture;public class Stable {public static String value(){return "stable";}}')
  put(root/'app/pom.xml','<project>'+parent+'''<artifactId>app</artifactId><dependencies><dependency><groupId>local.hot</groupId><artifactId>common</artifactId><version>1.0.0</version></dependency><dependency><groupId>local.hot</groupId><artifactId>stable</artifactId><version>1.0.0</version></dependency><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-websocket</artifactId></dependency><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-devtools</artifactId><optional>true</optional></dependency></dependencies><build><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin></plugins></build></project>''')
  message=root/'common/src/main/java/fixture/Message.java'
  def code(value,extra=''):return 'package fixture;public class Message {public static String value(){return "'+value+'";}'+extra+'}'
  put(message,code('v1'));removed=root/'common/src/main/java/fixture/Removed.java';put(removed,'package fixture;public class Removed {}')
  resource=root/'common/src/main/resources/marker.txt';put(resource,'r1')
  app=root/'app/src/main/java/fixture/App.java'
  app_code='''package fixture;import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.context.annotation.Bean;import org.springframework.web.socket.server.standard.ServerEndpointExporter;
@SpringBootApplication public class App { @Bean public ServerEndpointExporter exporter(){return new ServerEndpointExporter();} public static void main(String[] args){SpringApplication.run(App.class,args);} }'''
  put(app,app_code)
  probe=root/'app/src/main/java/fixture/Probe.java'
  probe_code='''package fixture;import java.util.*;import java.util.concurrent.atomic.*;import java.lang.management.*;import java.io.*;import org.springframework.web.bind.annotation.*;
@RestController public class Probe {private final String boot=UUID.randomUUID().toString();private final AtomicInteger count=new AtomicInteger();private final String marker="constructor-one";
@GetMapping("/probe") public Map<String,Object> probe()throws Exception{Map<String,Object> m=new LinkedHashMap<>();m.put("value",Message.value());m.put("pid",ManagementFactory.getRuntimeMXBean().getName());m.put("boot",boot);m.put("count",count.incrementAndGet());m.put("marker",marker);m.put("source",Message.class.getProtectionDomain().getCodeSource().getLocation().toString());m.put("java",System.getProperty("java.version"));m.put("restart",System.getProperty("spring.devtools.restart.enabled"));m.put("arg",System.getProperty("probe.spaces"));m.put("env",System.getenv("PROBE_ENV"));m.put("stable",Stable.value());try{Class.forName("fixture.Removed");m.put("removed",true);}catch(ClassNotFoundException e){m.put("removed",false);}try(InputStream in=getClass().getResourceAsStream("/marker.txt")){byte[] b=new byte[32];int n=in.read(b);m.put("resource",new String(b,0,n,"UTF-8"));}return m;} }'''
  put(probe,probe_code)
  put(root/'app/src/main/java/fixture/Room.java','''package fixture;import javax.websocket.*;import javax.websocket.server.*;import org.springframework.stereotype.Component;@Component @ServerEndpoint("/ws") public class Room {@OnMessage public String reply(String s){return Message.value();}}''')
  p=n.project(root,'热替换：真实多模块验收')
  c=n.api('config.save',{'project':p['id'],'config':{'id':'','name':'Spring HotSwap','cwd':'app','environment_id':java['id'],'launcher':{'kind':'spring-maven','target':'pom.xml','update_mode':'hotswap','arguments':['--server.port={port}','--server.address=127.0.0.1'],'properties':{'probe.spaces':'property with spaces'}},'watch':[],'env':{'PROBE_ENV':'env with spaces'}}})
  i=n.api('instance.save',{'project':p['id'],'instance':{'id':'','name':'Java8 instance','config_id':c['id'],'port':freeport(),'args':[],'env':{}}})
  first=start(n,p,i);report['initial']=first
  check('Selected Java 8 starts the real Spring Boot application',first['java'].startswith('1.8.') and first['value']=='v1')
  check('Runtime uses isolated workspace outputs, not installed stale JARs','hot-sessions' in first['source'] and 'target/classes' not in first['source'])
  check('DevTools cannot independently restart while applying a batch',first['restart']=='false')
  check('Visual-style properties and environment preserve spaces',first['arg']=='property with spaces' and first['env']=='env with spaces')
  check('Reported PID is actual Java, not the Maven parent',str(view(n,i)['pid'])==first['pid'].split('@')[0])
  stable=repo/'local/hot/stable/1.0.0/stable-1.0.0.jar';sig=signature(stable)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1560,'height':1100});page.set_default_timeout(20000);page.on('pageerror',lambda e:report['errors'].append(str(e)));page.goto(n.url)
   page.evaluate('''port=>new Promise((resolve,reject)=>{window.hotSocket=new WebSocket('ws://127.0.0.1:'+port+'/ws');window.hotClosed=0;hotSocket.onclose=()=>hotClosed++;hotSocket.onopen=resolve;hotSocket.onerror=reject})''',i['port'])
   def ws():return page.evaluate('''()=>new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('WS timeout')),5000);hotSocket.onmessage=e=>{clearTimeout(t);resolve(e.data)};hotSocket.send('same-connection')})''')
   check('Business WebSocket is really connected before update',ws()=='v1')
   before=view(n,i)['revision'];apply(n,p,i);wait_update(n,i,lambda v:v.get('update_status')=='current')
   check('No-change apply neither builds nor restarts',selections(n,c)[-1]['mode']=='reuse' and view(n,i)['revision']==before and response(i)['pid']==first['pid'])
   oldtime=message.stat();put(message,code('v2'));os.utime(message,ns=(oldtime.st_atime_ns,oldtime.st_mtime_ns));begin=time.monotonic()
   page.get_by_role('button',name='应用改动',exact=True).click()
   latest=wait_update(n,i,lambda v:(r:=response(i)) and r['value']=='v2' and r);report['timings']['body_edit_total_seconds']=round(time.monotonic()-begin,3)
   check('Method change returns new HTTP content without changing Java PID',latest['pid']==first['pid'])
   check('Existing bean identity and in-memory counter survive',latest['boot']==first['boot'] and latest['count']>first['count'])
   check('The SAME WebSocket stays open and runs new code',ws()=='v2' and page.evaluate('hotClosed')==0)
   check('Only changed module and downstream consumers rebuilt',set(selections(n,c)[-1]['selected'])=={'common','app'} and signature(stable)==sig)
   check('UI confirms actual hot replacement',view(n,i)['update_status']=='hotswapped')
   page.screenshot(path=str(OUT/'native-hot-050-applied.png'),full_page=True)
   # Schema change must not be silently accepted or silently restart the app.
   extra='public static int extra(){return 3;}'
   put(message,code('v3',extra));apply(n,p,i);wait_update(n,i,lambda v:v.get('pending_reason'))
   check('Adding a method asks for restart; no hidden cold restart',response(i)['value']=='v2' and response(i)['pid']==first['pid'] and ws()=='v2')
   expect(page.locator('.hot-pending')).to_be_visible();page.screenshot(path=str(OUT/'native-hot-050-pending.png'),full_page=True)
   page.get_by_role('button',name='重启实例',exact=True).click();latest=wait_update(n,i,lambda v:(r:=response(i)) and r['value']=='v3' and r)
   check('Explicit restart uses latest schema and a new JVM',latest['pid']!=first['pid'] and latest['boot']!=first['boot'])
   # Failed compiler deletes target/classes, but the old private runtime survives.
   put(message,'not valid Java');apply(n,p,i);wait_for(lambda:view(n,i).get('error'),240)
   check('Failed compile preserves working private runtime',response(i)['pid']==latest['pid'] and response(i)['value']=='v3')
   put(message,code('v4',extra));apply(n,p,i);new=wait_for(lambda:(r:=response(i)) and r['value']=='v4' and r,240)
   check('Retry after compile failure still hot swaps into the same JVM',new['pid']==latest['pid'] and new['boot']==latest['boot'])
   # File set changes, resources and constructor changes are all conservative.
   removed.unlink();apply(n,p,i);wait_update(n,i,lambda v:v.get('pending_reason'))
   check('Deleting a loaded class remains pending, not falsely unloaded',response(i)['removed'] is True and response(i)['pid']==new['pid'])
   latest=restart(n,p,i);check('Confirmed restart removes deleted class from actual classpath',latest['removed'] is False)
   put(resource,'r2');apply(n,p,i);wait_update(n,i,lambda v:v.get('pending_reason'))
   check('Resource edits do not leak from build output into old runtime',response(i)['resource']=='r1' and response(i)['pid']==latest['pid'])
   latest=restart(n,p,i);check('Resource is current after explicit restart',latest['resource']=='r2')
   put(probe,probe_code.replace('constructor-one','constructor-two'));apply(n,p,i);wait_update(n,i,lambda v:v.get('pending_reason'))
   check('Constructor/field initialization edit is not mislabelled hot',response(i)['marker']=='constructor-one' and response(i)['pid']==latest['pid'])
   latest=restart(n,p,i);check('Explicit restart applies new initialization',latest['marker']=='constructor-two')
   # Change a mapping annotation without changing method signatures.
   annotated=probe_code.replace('constructor-one','constructor-two').replace('@GetMapping("/probe")','@GetMapping(value="/probe", produces="application/json")')
   put(probe,annotated);apply(n,p,i);wait_update(n,i,lambda v:v.get('pending_reason'))
   check('Annotation changes require refresh/restart rather than stale Spring metadata',response(i)['pid']==latest['pid'])
   restart(n,p,i)
   # Invalid agent authentication cannot redefine any class.
   endpoints=list((n.root/'data/build-state/hot-sessions').rglob('endpoint'));assert len(endpoints)==1
   port=int(endpoints[0].read_text().splitlines()[0]);before=response(i)
   with socket.create_connection(('127.0.0.1',port),timeout=3) as sock:
    def send(s):b=s.encode();sock.sendall(struct.pack('>I',len(b))+b)
    send('NOIDE-HS1');send('wrong-token');sock.recv(4096)
   check('Unauthenticated agent control does not alter application',response(i)['pid']==before['pid'] and response(i)['value']==before['value'])
   # A second actual JVM on Java17 must use its own authenticated agent.
   second=n.api('instance.save',{'project':p['id'],'instance':{'id':'','name':'Java17 instance','config_id':c['id'],'environment_id':java17['id'],'port':freeport(),'args':[],'env':{}}})
   r17=start(n,p,second);old8=response(i);put(message,code('v5',extra));apply(n,p,i)
   a8=wait_for(lambda:(r:=response(i)) and r['value']=='v5' and r,240);a17=wait_for(lambda:(r:=response(second)) and r['value']=='v5' and r,240)
   check('Two JVMs including Java17 both update without restarting',a8['pid']==old8['pid'] and a17['pid']==r17['pid'] and a17['java'].startswith('17.'))
   old17=a17['pid'];restart(n,p,i);check('Restart instance does not restart another instance',response(second)['pid']==old17)
   stop(n,p,i);stop(n,p,second)
   c['watch']=['app/src'];n.api('config.save',{'project':p['id'],'config':c});watched=start(n,p,i);put(message,code('v6',extra))
   updated=wait_for(lambda:(r:=response(i)) and r['value']=='v6' and r,240)
   check('Sibling-module file watcher also hot swaps, without manual button',updated['pid']==watched['pid'])
   check('Unrelated broken module is never compiled',not(root/'unrelated/target').exists())
   check('Unchanged upstream JAR stays byte-and-timestamp identical',signature(stable)==sig)
   stop(n,p,i);page.get_by_role('button',name='刷新状态',exact=True).click();page.locator('.run-config-card').get_by_role('button',name='编辑配置',exact=True).click();expect(page.get_by_label('代码更新方式',exact=True)).to_have_value('hotswap');page.screenshot(path=str(OUT/'native-hot-050-config.png'),full_page=True)
   check('User can view and change hot/restart mode visually')
   check('No uncaught browser errors',not report['errors']);browser.close()
  report['health']=json.load(urllib.request.urlopen(n.base+'/api/health'))
  check('Private runtime directories are removed after both instances stop',not list((n.root/'data/build-state/hot-sessions').glob('instance-*')))
try:main();report['passed']=True
except Exception as e:report['failure']=str(e);raise
finally:(OUT/'native-hot-050.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
