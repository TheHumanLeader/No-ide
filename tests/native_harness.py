"""Disposable real-native test harness; never touches user projects or settings."""
import json, os, pathlib, shutil, signal, subprocess, tempfile, time
import urllib.request, urllib.parse, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[1]

def wait_for(fn, timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=fn()
        if value:return value
        time.sleep(.1)
    raise AssertionError('Timed out waiting for test condition')

def cli(*args,cwd=None):
    p=subprocess.run([str(a) for a in args],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
    assert p.returncode==0,(args,p.stderr.decode(errors='replace'))
    return p.stdout.decode('utf-8',errors='replace').strip()

class Native:
    def __enter__(self):
        self.temp=tempfile.TemporaryDirectory(prefix='no-ide-v04-')
        self.root=pathlib.Path(self.temp.name)
        self.proc=None
        self.start()
        return self
    def start(self):
        self.log_path=self.root/'startup.log'
        exe=os.environ.get('NO_IDE_TEST_EXE',str(ROOT/'backend/target/release'/('no-ide.exe' if os.name=='nt' else 'no-ide')))
        web=os.environ.get('NO_IDE_TEST_WEB',str(ROOT/'dist'))
        with self.log_path.open('w') as log:
            self.proc=subprocess.Popen([exe,'--no-open','--port','0','--data-dir',str(self.root/'data'),'--web-dir',web],stdout=log,stderr=subprocess.STDOUT)
        def startup():
            t=self.log_path.read_text(encoding='utf8',errors='replace')
            assert self.proc.poll() is None,t
            return next((x.split('=',1)[1] for x in t.splitlines() if x.startswith('NO_IDE_URL=')),None)
        self.url=wait_for(startup)
        self.base=self.url.split('#')[0].rstrip('/')
        self.token=urllib.parse.parse_qs(urllib.parse.urlparse(self.url).fragment)['token'][0]
    def api(self,action,params=None,status=200):
        r=urllib.request.Request(self.base+'/api/call',data=json.dumps({'action':action,'params':params or {}}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+self.token})
        try:
            with urllib.request.urlopen(r,timeout=150) as response:code=response.status;body=response.read()
        except urllib.error.HTTPError as e:code=e.code;body=e.read()
        assert code==status,(action,code,body[:2000])
        return json.loads(body) if body else None
    def project(self,path,name):
        return self.api('project.add',{'root':str(path),'name':name,'confirmed':True})
    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                for p in self.api('state')['store']['projects']:
                    for i in p['instances']:
                        self.api('run.stop',{'project':p['id'],'instance':i['id']})
                time.sleep(.2)
            except Exception:pass
            if os.name=='nt':self.proc.terminate()
            else:self.proc.send_signal(signal.SIGINT)
            try:self.proc.wait(8)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
    def __exit__(self,*args):
        self.stop();self.temp.cleanup()
