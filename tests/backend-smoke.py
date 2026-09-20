"""Native integration tests. All writes use disposable local test repositories.
No user's source repository, credentials or external remote is modified.
"""
import json, os, pathlib, platform, shutil, signal, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.parse, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[1]
EXE = pathlib.Path(os.environ.get('NO_IDE_TEST_EXE', str(ROOT / 'backend/target/release' / ('no-ide.exe' if os.name=='nt' else 'no-ide'))))
WEB = pathlib.Path(os.environ.get('NO_IDE_TEST_WEB', str(ROOT/'dist')))
checks=[]
def check(name, condition=True):
    assert condition, name
    checks.append(name)
    print('PASS:',name,flush=True)
def cli(*args,cwd=None):
    r=subprocess.run([str(a) for a in args],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
    if r.returncode: raise AssertionError(f'Fixture command {args[0]} failed: {r.stderr.decode("utf-8",errors="replace")}')
    return r.stdout.decode('utf-8',errors='strict').strip()
def wait_for(fn,seconds=20):
    end=time.monotonic()+seconds;last=None
    while time.monotonic()<end:
        try:
            last=fn()
            if last:return last
        except (ConnectionError,OSError,urllib.error.URLError): pass
        time.sleep(.15)
    raise AssertionError(f'Condition timeout; last={last!r}')
def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.2):return True
    except OSError:return False

with tempfile.TemporaryDirectory(prefix='no-ide-integration-') as tmp:
    tmp=pathlib.Path(tmp);out=tmp/'startup.log';report={'platform':platform.platform(),'checks':checks,'scope':'Temporary local fixtures; no GUI picker / external authenticated remote tested'}
    proc=None;api=None;projects=[]
    try:
        with out.open('w') as f:
            proc=subprocess.Popen([str(EXE),'--no-open','--port','0','--data-dir',str(tmp/'data'),'--web-dir',str(WEB)],stdout=f,stderr=subprocess.STDOUT)
        def startup():
            lines=out.read_text(encoding='utf-8',errors='replace').splitlines()
            if proc.poll() is not None: raise AssertionError('\n'.join(lines))
            return next((x.split('=',1)[1] for x in lines if x.startswith('NO_IDE_URL=')),None)
        url=wait_for(startup);base=url.split('#')[0].rstrip('/');token=urllib.parse.parse_qs(urllib.parse.urlparse(url).fragment)['token'][0]
        def api(action,params=None,expected=200,headers=None):
            h={'Content-Type':'application/json','Authorization':'Bearer '+token};h.update(headers or {})
            req=urllib.request.Request(base+'/api/call',data=json.dumps({'action':action,'params':params or {}}).encode(),headers=h)
            try:
                with urllib.request.urlopen(req,timeout=150) as r:code=r.status;body=r.read()
            except urllib.error.HTTPError as e:code=e.code;body=e.read()
            assert code==expected,(action,code,body[:1500].decode('utf-8',errors='replace'))
            if not body:return None
            return json.loads(body)
        def register(path,name):
            p=api('project.add',{'root':str(path),'name':name,'confirmed':True});projects.append(p);return p
        def state(i):return next((r for r in api('state')['runs'] if r['instance']==i['id']),{})
        def run(p,i,op):return api('run.'+op,{'project':p['id'],'instance':i['id']})
        def ready(i):
            s=state(i)
            if s.get('state')=='error':raise AssertionError(s)
            return s if s.get('state')=='running' else False
        health=json.load(urllib.request.urlopen(base+'/api/health'));report['health']=health
        check('Native HTTP starts and reports actual platform',health['name']=='no-ide')
        api('state',expected=401,headers={'Authorization':''});check('Unauthenticated control is rejected')
        api('state',expected=403,headers={'Origin':'https://untrusted.example'});check('Cross-origin control is rejected')
        api('state',expected=403,headers={'Host':'untrusted.example'});check('Untrusted Host is rejected')
        tools=api('tools.detect');report['tools']=tools
        check('Git is discovered and version-tested',bool(tools['git']['selected']))
        check('SVN is discovered and version-tested',bool(tools['svn']['selected']))
        git=tools['git']['selected']['path'];svn=tools['svn']['selected']['path']
        api('tools.save',{'settings':{'git':str(tmp/'missing-git')}},expected=400)
        check('Invalid manual client is rejected without saving',api('state')['store']['tools']['git'] is None)
        api('tools.save',{'settings':{'git':git,'svn':svn}})
        check('Global client configuration persists',api('state')['store']['tools']['git']==git)
        app=tmp/'project with spaces';app.mkdir();(app/'src').mkdir();(app/'src/value.txt').write_text('ONE',encoding='utf-8')
        (app/'build.py').write_text("import pathlib,sys,time\np=pathlib.Path('build-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\nv=pathlib.Path('src/value.txt').read_text()\nprint('BUILD '+v,flush=True)\nif v=='SLOW': time.sleep(15)\nsys.exit(2 if v=='FAIL' else 0)\n",encoding='utf-8')
        (app/'app.py').write_text("import http.server,pathlib,sys,os,subprocess\nv=pathlib.Path('src/value.txt').read_text();port=int(sys.argv[1]);assert int(os.environ['PORT'])==port\nif os.environ.get('CHILD_PORT'): subprocess.Popen([sys.executable,'-u','-m','http.server',os.environ['CHILD_PORT'],'--bind','127.0.0.1'])\nclass Handler(http.server.BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(v.encode())\nserver=http.server.HTTPServer(('127.0.0.1',port),Handler)\nprint('READY '+str(port),flush=True)\nserver.serve_forever()\n",encoding='utf-8')
        p=register(app,'Integration project');api('tools.save',{'project':p['id'],'settings':{'git':git}})
        scoped=api('tools.detect',{'project':p['id']})
        check('Project override is selected',scoped['git']['selected']['source']=='项目指定')
        cfg={'id':'','name':'Python HTTP','cwd':'.','command':{'program':sys.executable,'args':['-u','app.py','{port}']},'build':{'program':sys.executable,'args':['-u','build.py']},'watch':['src'],'env':{}}
        c=api('config.save',{'project':p['id'],'config':cfg})
        bad={**cfg,'id':'','cwd':'../'};api('config.save',{'project':p['id'],'config':bad},expected=400);check('Working directory traversal is rejected')
        a,b,child=free_port(),free_port(),free_port()
        i1=api('instance.save',{'project':p['id'],'instance':{'id':'','name':'first','config_id':c['id'],'port':a,'args':[],'env':{'CHILD_PORT':str(child)}}})
        i2=api('instance.save',{'project':p['id'],'instance':{'id':'','name':'second','config_id':c['id'],'port':b,'args':[],'env':{}}})
        api('instance.save',{'project':p['id'],'instance':{**i2,'id':'','port':a}},expected=400);check('Duplicate configured ports are rejected')
        run(p,i1,'start');s1=wait_for(lambda:ready(i1));run(p,i2,'start');s2=wait_for(lambda:ready(i2))
        wait_for(lambda:port_open(child));check('Two real instances and a child process run on separate ports',a!=b and s1['pid']!=s2['pid'])
        check('Port placeholder and PORT environment reach the actual app',urllib.request.urlopen(f'http://127.0.0.1:{a}').read()==b'ONE')
        check('Initial build is shared by same-configuration instances',(app/'build-count').read_text()=='1')
        time.sleep(.5);(app/'src/value.txt').write_text('TWO',encoding='utf-8')
        def updated():
            x,y=ready(i1),ready(i2)
            return x and y and x['revision']>s1['revision'] and y['revision']>s2['revision'] and urllib.request.urlopen(f'http://127.0.0.1:{a}').read()==b'TWO'
        wait_for(updated);check('Filesystem watcher rebuilds and restarts both instances with changed output')
        s1,s2=state(i1),state(i2);(app/'src/value.txt').write_text('FAIL',encoding='utf-8')
        wait_for(lambda:state(i1).get('error') and state(i2).get('error'))
        check('Failed build retains both old process IDs',state(i1)['pid']==s1['pid'] and state(i2)['pid']==s2['pid'])
        check('Old app still answers after failed build',urllib.request.urlopen(f'http://127.0.0.1:{a}').read()==b'TWO')
        run(p,i1,'stop');wait_for(lambda:state(i1).get('state')=='stopped');wait_for(lambda:not port_open(a) and not port_open(child));check('Stopping an instance kills its owned child process')
        check('Stopping first instance does not stop the second',port_open(b))
        (app/'src/value.txt').write_text('SLOW',encoding='utf-8');wait_for(lambda:state(i2).get('state')=='building');run(p,i2,'stop');wait_for(lambda:state(i2).get('state')=='stopped');time.sleep(.8)
        check('Stop cancels an active build and does not resurrect the instance',not port_open(b))
        log=api('logs');check('Logs contain actual stdout and failed build output',any('READY' in x['text'] for x in log) and any('FAIL' in x['text'] for x in log))
        work=tmp/'git fixture';work.mkdir();bare=tmp/'origin.git';cli(git,'init','--bare',bare);cli(git,'init','-b','main',cwd=work);cli(git,'config','user.name','No-ide integration',cwd=work);cli(git,'config','user.email','integration@example.invalid',cwd=work)
        for f in ['a file.txt','keep.txt']:(work/f).write_text('old\n',encoding='utf-8')
        cli(git,'add','.',cwd=work);cli(git,'commit','-m','initial',cwd=work);cli(git,'remote','add','origin',str(bare),cwd=work);cli(git,'push','-u','origin','main',cwd=work)
        pg=register(work,'Git fixture');rg=pg['repos'][0]['id'];common={'project':pg['id'],'repo':rg}
        def prep(op,paths=None,msg='integration change'):return api('vcs.prepare',{**common,'operation':op,'paths':paths or [],'message':msg})
        def execute(plan):return api('vcs.execute',{**common,'token':plan['token'],'confirmed':True})
        (work/'a file.txt').write_text('new\n',encoding='utf-8');(work/'keep.txt').write_text('keep local\n',encoding='utf-8')
        status=api('vcs.status',common);check('Git status reads two real changed files',len(status['files'])==2)
        diff=api('vcs.diff',{**common,'path':'a file.txt'})['diff'];check('Git Diff shows actual old and new lines','-old' in diff and '+new' in diff)
        api('vcs.diff',{**common,'path':'../outside'},expected=400);check('VCS path traversal is rejected')
        stale=prep('stage',['a file.txt']);(work/'a file.txt').write_text('newer\n',encoding='utf-8');api('vcs.execute',{**common,'token':stale['token'],'confirmed':True},expected=400);check('Changed file invalidates a prepared operation')
        staged_plan=prep('stage',['a file.txt']);execute(staged_plan);api('vcs.execute',{**common,'token':staged_plan['token'],'confirmed':True},expected=400);check('Confirmation token cannot be replayed')
        old_remote=cli(git,'rev-parse','refs/heads/main',cwd=bare)
        plan=prep('commit');check('Git commit confirmation lists the actual staged file set',plan['paths']==['a file.txt']);execute(plan)
        check('Git commit preserves unselected worktree changes',cli(git,'status','--porcelain',cwd=work).strip()=='M keep.txt')
        check('Git local commit does not change remote',cli(git,'rev-parse','refs/heads/main',cwd=bare)==old_remote)
        execute(prep('push'));check('Explicit Git push changes only confirmed remote branch',cli(git,'rev-parse','refs/heads/main',cwd=bare)==cli(git,'rev-parse','HEAD',cwd=work))
        api('vcs.prepare',{**common,'operation':'pull','paths':[]},expected=400);check('Pull does not discard uncommitted files')
        execute(prep('stage',['keep.txt']));execute(prep('commit'));execute(prep('push'))
        other=tmp/'other';cli(git,'clone','--branch','main',str(bare),other);cli(git,'config','user.name','Test',cwd=other);cli(git,'config','user.email','test@example.invalid',cwd=other)
        (other/'remote.txt').write_text('from remote',encoding='utf-8');cli(git,'add','remote.txt',cwd=other);cli(git,'commit','-m','remote',cwd=other);cli(git,'push','origin','main',cwd=other);execute(prep('pull'));check('Git fast-forward pull retrieves real remote changes',(work/'remote.txt').read_text()=='from remote')
        svnadmin=pathlib.Path(svn).with_name('svnadmin.exe' if os.name=='nt' else 'svnadmin')
        if not svnadmin.is_file():svnadmin=pathlib.Path(shutil.which('svnadmin') or '')
        assert svnadmin.is_file(),'svnadmin test tool missing'
        server=tmp/'svn-repo';wc=tmp/'svn-wc';cli(svnadmin,'create',server);repo_url=server.as_uri();cli(svn,'checkout',repo_url,wc,'--non-interactive')
        for f in ['a.txt','keep.txt']:(wc/f).write_text('old\n',encoding='utf-8')
        cli(svn,'add','a.txt','keep.txt',cwd=wc);cli(svn,'commit','-m','initial','--non-interactive',cwd=wc)
        ps=register(wc,'SVN fixture');common={'project':ps['id'],'repo':ps['repos'][0]['id']}
        (wc/'a.txt').write_text('new svn\n',encoding='utf-8');(wc/'keep.txt').write_text('keep svn local\n',encoding='utf-8')
        status=api('vcs.status',common);check('SVN XML status reads real changed files',len(status['files'])==2)
        diff=api('vcs.diff',{**common,'path':'a.txt'})['diff'];check('SVN Diff reads BASE versus working copy','-old' in diff and '+new svn' in diff)
        plan=prep('commit',['a.txt']);execute(plan)
        check('SVN commit leaves unchecked file uncommitted','keep.txt' in cli(svn,'status',cwd=wc) and 'a.txt' not in cli(svn,'status',cwd=wc))
        check('SVN selected commit reaches repository immediately',cli(svn,'cat',repo_url+'/a.txt')=='new svn')
        api('vcs.prepare',{**common,'operation':'update','paths':[]},expected=400);check('SVN update protects pending local changes')
        execute(prep('commit',['keep.txt']));execute(prep('update'));check('SVN clean update succeeds',not cli(svn,'status',cwd=wc))
        saved=json.loads((tmp/'data/settings.json').read_text(encoding='utf-8'));check('Projects, instances and tool overrides are persisted',len(saved['projects'])==3 and len(saved['projects'][0]['instances'])==2)
        report['passed']=True
    except Exception as e:
        report['passed']=False;report['error']=str(e);raise
    finally:
        dest=ROOT/'test-results';dest.mkdir(exist_ok=True)
        (dest/('native-'+platform.system()+'-'+platform.machine()+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if proc and proc.poll() is None:
            if api:
                try:
                    for p in api('state')['store']['projects']:
                        for i in p['instances']:
                            try:api('run.stop',{'project':p['id'],'instance':i['id']})
                            except Exception:pass
                    time.sleep(.4)
                except Exception:pass
            if os.name=='nt':proc.terminate()
            else:proc.send_signal(signal.SIGINT)
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
print(f'Passed {len(checks)} real native checks on {platform.system()} / {platform.machine()}')
