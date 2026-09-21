"""Real legacy-output regression; only disposable test projects.
Chinese paths are tested by native processes. The Java 8/Maven Unicode-install
baseline is recorded separately, because an upstream launcher failure is not
an output-decoder failure. Never change the system locale or switch user SDKs.
"""
import hashlib, json, os, pathlib, platform, shutil, socket, subprocess, sys, time, urllib.request
from contextlib import contextmanager
from native_harness import Native, ROOT, cli, wait_for

OUT=ROOT/'test-results'; OUT.mkdir(exist_ok=True)
checks=[]; details={}
def check(name,condition=True):
    assert condition,name
    checks.append(name);print('PASS',name,flush=True)
def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def state(n,iid):return next((x for x in n.api('state')['runs'] if x['instance']==iid),{})
def fetch_json(port,path='/'):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=1) as r:return json.load(r)
    except (OSError,ValueError):return False
def start(n,pid,i,path='/'):
    n.api('run.start',{'project':pid,'instance':i['id']})
    def ready():
        s=state(n,i['id'])
        if s.get('state')=='error':raise AssertionError({'state':s,'logs':n.api('logs')[-12:]})
        return fetch_json(i['port'],path)
    return wait_for(ready,100)
def stop(n,pid,i):
    n.api('run.stop',{'project':pid,'instance':i['id']});wait_for(lambda:state(n,i['id']).get('state')=='stopped')
def logs(n,key,stream):return ''.join(x['text'] for x in n.api('logs') if x['instance']==key and x['stream']==stream)
@contextmanager
def inherited(**values):
    before={k:os.environ.get(k) for k in values};os.environ.update(values)
    try:yield
    finally:
        for k,v in before.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

def native_regressions():
    with Native() as n:
        root=n.root/'中文项目 有空格'/'源码'/'trunk'/'pms';root.mkdir(parents=True)
        build=root/'构建.py';app=root/'应用.py'
        build.write_text('''import pathlib, sys
bad=pathlib.Path('fail.txt').exists()
sys.stdout.buffer.write(('构建日志：中文目录 '+str(pathlib.Path.cwd())+'\\n').encode('gbk'));sys.stdout.buffer.flush()
if bad:
 sys.stderr.buffer.write('真实构建错误：故意失败\\n'.encode('gbk'));sys.stderr.buffer.flush();sys.exit(7)
''',encoding='utf8')
        app.write_text('''import http.server, threading, os, pathlib, json, time, sys
class H(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  data=json.dumps({'cwd':str(pathlib.Path.cwd()),'marker':'实际进程已运行'},ensure_ascii=False).encode('utf8')
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
 def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',int(os.environ['PORT'])),H)
threading.Thread(target=server.serve_forever,daemon=True).start()
for sink,text in [(sys.stdout.buffer,'运行中文输出：启动成功\\n'),(sys.stderr.buffer,'运行中文错误流：正常测试\\n')]:
 for b in text.encode('gbk'):
  sink.write(bytes([b]));sink.flush();time.sleep(.004)
while True: time.sleep(1)
''',encoding='utf8')
        originals={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (build,app)}
        raw=subprocess.run([sys.executable,str(build)],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
        try:raw.decode('utf8');invalid=False
        except UnicodeDecodeError:invalid=True
        check('Real build writes legacy bytes that would fail strict UTF-8',invalid)
        details['build_non_utf8_hex']=raw[:100].hex()
        p=n.project(root,'中文输出回归');pid=p['id']
        config={'id':'','name':'旧配置兼容','cwd':'.','command':{'program':sys.executable,'args':[str(app)]},'build':{'program':sys.executable,'args':[str(build)]},'env':{},'watch':[]}
        c=n.api('config.save',{'project':pid,'config':config})
        check('Old configuration without encoding migrates to auto',c['output_encoding']=='auto')
        i=n.api('instance.save',{'project':pid,'instance':{'id':'','name':'中文实例','config_id':c['id'],'port':free_port(),'args':[],'env':{}}})
        result=start(n,pid,i)
        check('Default mode launches after successful non-UTF-8 build',result['marker']=='实际进程已运行')
        check('Chinese working directory is not reconstructed from log output',pathlib.Path(result['cwd']).samefile(root))
        stop(n,pid,i);c['output_encoding']='gbk';c=n.api('config.save',{'project':pid,'config':c});start(n,pid,i)
        wait_for(lambda:'运行中文错误流：正常测试' in logs(n,i['id'],'stderr'))
        check('GBK stdout survives one-byte pipe writes','运行中文输出：启动成功' in logs(n,i['id'],'stdout'))
        check('GBK stderr survives one-byte pipe writes','运行中文错误流：正常测试' in logs(n,i['id'],'stderr'))
        check('GBK build logs display Chinese text','构建日志：中文目录' in logs(n,c['id'],'build'))
        old=state(n,i['id']);(root/'fail.txt').write_text('fail',encoding='ascii')
        n.api('run.update',{'project':pid,'instance':i['id']})
        failed=wait_for(lambda:state(n,i['id']) if state(n,i['id']).get('error') else False)
        check('Nonzero GBK build reports actual exit code, not decoding failure','7' in failed['error'] and '真实构建错误' in failed['error'] and 'UTF-8' not in failed['error'])
        check('Failed build preserves previous PID and HTTP response',failed['pid']==old['pid'] and bool(fetch_json(i['port'])))
        stop(n,pid,i);(root/'fail.txt').unlink()
        c['output_encoding']='unsupported';n.api('config.save',{'project':pid,'config':c},status=400)
        check('Unsupported decoding policy is rejected before save')
        n.stop();n.start();saved=n.api('state')['store']['projects'][0]['configs'][0]
        check('Encoding policy persists across actual executor restart',saved['output_encoding']=='gbk')
        check('No source content was changed by output decoding',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in originals.items()))
        git=shutil.which('git');assert git
        repo=root/'仓库';repo.mkdir();cli(git,'init','-b','main',cwd=repo)
        cli(git,'config','user.name','Encoding test',cwd=repo);cli(git,'config','user.email','test@example.invalid',cwd=repo)
        (repo/'中文文件.txt').write_text('old\n',encoding='utf8');cli(git,'add','.',cwd=repo);cli(git,'commit','-m','base',cwd=repo)
        (repo/'中文文件.txt').write_text('new\n',encoding='utf8')
        rr=n.api('repo.add',{'project':pid,'path':'仓库'});rs=n.api('vcs.status',{'project':pid,'repo':rr['id']})
        check('Strict Git status still preserves Chinese file names',any(f['path']=='中文文件.txt' for f in rs['files']))
        n.api('vcs.diff',{'project':pid,'repo':rr['id'],'path':'../escape'},status=400)
        check('Log charset support does not relax repository path validation')

def maven_regression():
    opts='-Dsun.stdout.encoding=GBK -Dsun.stderr.encoding=GBK -Dstyle.color=never'
    with inherited(MAVEN_OPTS=opts):
      with Native() as n:
        java=os.environ['TEST_JAVA8'];e=n.api('environments.save',{'kind':'java','path':java,'name':'Java 8 中文回归','default':True})
        check('Java8 selected for legacy Maven output test',e['major']==8)
        mvn=shutil.which('mvn.cmd');assert mvn
        home=pathlib.Path(mvn).resolve().parent.parent;install=n.root/'构建工具 Maven 有空格';shutil.copytree(home,install)
        import ctypes
        details['windows_ansi_code_page']=ctypes.windll.kernel32.GetACP();probe=[]
        for label,options in [('system-default',''),('old-forced-file-encoding','-Dfile.encoding=GBK '+opts),('stdout-stderr-only',opts)]:
            direct=subprocess.run([str(install/'bin/mvn.cmd'),'--version'],cwd=n.root,env={**os.environ,'JAVA_HOME':java,'MAVEN_OPTS':options},stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,shell=True)
            probe.append({'mode':label,'exit_code':direct.returncode,'stdout_hex':direct.stdout[-2048:].hex(),'stderr':direct.stderr.decode('utf8',errors='replace')})
        details['direct_maven_version_probes']=probe
        unicode_maven_ok=probe[0]['exit_code']==0 and probe[2]['exit_code']==0
        details['upstream_java8_unicode_maven_supported']=unicode_maven_ok
        if not unicode_maven_ok:
            # Not a decoder error: the unmodified upstream launcher also fails.
            # Keep that failure explicit. Do not pretend the Unicode case passed,
            # change machine locale, rewrite source, or silently switch Java.
            details['known_limitations']=['On this Windows host Java 8 cannot start unmodified Maven from the Chinese installation path, even with default JVM options. This external path compatibility is NOT fixed by log decoding.']
            install=n.root/'Maven tools with spaces';shutil.copytree(home,install)
        details['maven_fixture_uses_chinese_paths']=unicode_maven_ok
        baseline=subprocess.run([str(install/'bin/mvn.cmd'),'--version'],cwd=n.root,env={**os.environ,'JAVA_HOME':java},stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,shell=True)
        check('Real Maven baseline starts independently of No-ide',baseline.returncode==0)
        n.api('build_tools.save',{'kind':'maven','path':str(install)})
        tool=n.api('build_tools.detect')['maven'];check('Maven version detection accepts localized output',tool['version'].startswith('Apache Maven '));details['maven_version']=tool['version']
        exe=pathlib.Path(tool['selected']['path'])
        root=n.root/('数字化平台 中文路径' if unicode_maven_ok else 'PMS project with spaces');module=root/('源码/trunk/pms/pms-admin' if unicode_maven_ok else 'source/trunk/pms/pms-admin');module.mkdir(parents=True)
        (module/'pom.xml').write_text('''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.18</version><relativePath/></parent><groupId>local.noide</groupId><artifactId>encoding-test</artifactId><version>1.0</version><properties><java.version>1.8</java.version><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency></dependencies><build><plugins><plugin><groupId>org.springframework.boot</groupId><artifactId>spring-boot-maven-plugin</artifactId></plugin><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-antrun-plugin</artifactId><version>3.1.0</version><executions><execution><phase>validate</phase><configuration><target><echo message="构建输出中文编码探针"/></target></configuration><goals><goal>run</goal></goals></execution></executions></plugin></plugins></build></project>''',encoding='utf8')
        src=module/'src/main/java/fixture/App.java';src.parent.mkdir(parents=True)
        src.write_text('''package fixture;
import java.util.*;import org.springframework.boot.*;import org.springframework.boot.autoconfigure.*;import org.springframework.web.bind.annotation.*;
@SpringBootApplication @RestController public class App {
@GetMapping("/probe") public Map<String,String> probe(){Map<String,String> m=new LinkedHashMap<>();m.put("java",System.getProperty("java.version"));m.put("property",System.getProperty("probe.property"));m.put("cwd",System.getProperty("user.dir"));return m;}
public static void main(String[] args) throws Exception {System.out.write("应用日志中文探针\\n".getBytes("GBK"));System.out.flush();System.err.write("错误日志中文探针\\n".getBytes("GBK"));System.err.flush();SpringApplication.run(App.class,args);}}
''',encoding='utf8')
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [src,module/'pom.xml']}
        settings=n.root/('构建配置 settings.xml' if unicode_maven_ok else 'Maven configuration settings.xml');settings.write_text('<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"/>',encoding='utf8')
        cache=n.root/('中文依赖 仓库' if unicode_maven_ok else 'Maven dependencies repository');cache.mkdir()
        n.api('build_tools.save',{'kind':'maven_settings','path':str(settings)});n.api('build_tools.save',{'kind':'maven_repository','path':str(cache)})
        args=[str(exe),'--batch-mode','--no-transfer-progress','--settings',str(settings),f'-Dmaven.repo.local={cache}','-DskipTests','package','spring-boot:help']
        warm=subprocess.run(args,cwd=module,env={**os.environ,'JAVA_HOME':java},stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300,shell=True)
        (OUT/'native-042-maven-raw.log').write_bytes(warm.stdout+warm.stderr)
        assert warm.returncode==0,(warm.returncode,warm.stderr[-1000:],warm.stdout[-2000:])
        try:warm.stdout.decode('utf8');invalid=False
        except UnicodeDecodeError:invalid=True
        check('Actual Maven build stdout is non-UTF-8',invalid)
        check('Actual Maven output includes GBK Chinese marker','构建输出中文编码探针'.encode('gbk') in warm.stdout);details['maven_output_is_gbk']=True
        p=n.project(root,'数字化平台 · 中文回归');pid=p['id']
        entry=next(x for x in n.api('project.discover',{'project':pid})['entries'] if x['kind']=='spring-maven')
        c=n.api('config.save',{'project':pid,'config':{'id':'','name':'pms-admin · 中文输出回归','cwd':entry['cwd'],'environment_id':e['id'],'command':{'program':'auto','args':[]},'watch':[],'env':{},'launcher':{'kind':'spring-maven','target':entry['target'],'arguments':['--server.port={port}','--server.address=127.0.0.1'],'vm_options':['-Dsun.stdout.encoding=GBK','-Dsun.stderr.encoding=GBK'],'properties':{'probe.property':'value with spaces'}}}})
        i=n.api('instance.save',{'project':pid,'instance':{'id':'','name':'数字化平台','config_id':c['id'],'environment_id':e['id'],'port':free_port(),'args':[],'env':{}}})
        result=start(n,pid,i,'/probe');details['spring_response']=result
        check('Default mode runs real Spring Boot after GBK Maven compile',result['java'].startswith('1.8.') and result['property']=='value with spaces')
        check('Actual Java process receives the exact configured directory',pathlib.Path(result['cwd']).samefile(module));stop(n,pid,i)
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as pw:
            b=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
            page=b.new_page(viewport={'width':1440,'height':1100});page.set_default_timeout(30000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(n.url);page.locator('.run-config-card').get_by_role('button',name='编辑配置',exact=True).click()
            page.locator('.visual-advanced summary').click();expect(page.get_by_label('日志编码',exact=True)).to_have_value('auto')
            page.get_by_label('日志编码',exact=True).select_option('gbk');page.screenshot(path=str(OUT/'native-042-output-encoding.png'),full_page=True)
            page.get_by_role('button',name='保存配置',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
            saved=n.api('state')['store']['projects'][0]['configs'][0]
            check('UI can persist GBK log display without changing JVM properties',saved['output_encoding']=='gbk' and saved['id']==c['id'] and saved['launcher']==c['launcher'])
            page.locator('.live-instance').get_by_role('button',name='运行',exact=True).click();wait_for(lambda:fetch_json(i['port'],'/probe'),100)
            wait_for(lambda:'应用日志中文探针' in logs(n,i['id'],'stdout'))
            check('Actual Maven build log is readable under GBK display','构建输出中文编码探针' in logs(n,c['id'],'build'))
            check('Actual Spring stdout is readable under GBK display','应用日志中文探针' in logs(n,i['id'],'stdout'))
            all_runtime=logs(n,i['id'],'stdout')+logs(n,i['id'],'stderr')
            check('Actual Spring stderr is captured and readable','错误日志中文探针' in all_runtime)
            page.screenshot(path=str(OUT/'native-042-chinese-running.png'),full_page=True)
            check('No uncaught browser error in real encoding workflow',not errors);b.close()
        stop(n,pid,i)
        check('Maven/Spring source files remain byte-for-byte unchanged',all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items()))

if __name__=='__main__':
    report={'platform':platform.platform(),'checks':checks,'details':details,'passed':False,'scope':'Chinese paths are tested with native processes. Actual Java 8 Maven Spring build verifies GBK output separately; upstream Unicode-installation failures are recorded as known limitations, not reported as passes. No system code pages or user projects are changed.'}
    try:
        native_regressions()
        if os.name=='nt':maven_regression()
        report['passed']=True
    except Exception as e:report['error']=str(e);raise
    finally:(OUT/'native-encoding-042.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
