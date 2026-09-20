"""Initial native HTTP/client smoke check; extended integration cases follow."""
import json, os, pathlib, subprocess, tempfile, time, urllib.request, urllib.parse
root=pathlib.Path(__file__).resolve().parents[1]
exe=root/'backend/target/release'/('no-ide.exe' if os.name=='nt' else 'no-ide')
with tempfile.TemporaryDirectory() as d:
    out=pathlib.Path(d)/'startup.txt'
    with out.open('w') as f:
        p=subprocess.Popen([str(exe),'--no-open','--port','0','--data-dir',str(pathlib.Path(d)/'data'),'--web-dir',str(root/'dist')],stdout=f,stderr=subprocess.STDOUT)
    try:
        url=None
        for _ in range(100):
            lines=out.read_text(encoding='utf-8',errors='replace').splitlines()
            urls=[x.split('=',1)[1] for x in lines if x.startswith('NO_IDE_URL=')]
            if urls:url=urls[0];break
            if p.poll() is not None:raise RuntimeError('\n'.join(lines))
            time.sleep(.1)
        assert url,'No startup URL'
        base=url.split('#')[0].rstrip('/')
        token=urllib.parse.parse_qs(urllib.parse.urlparse(url).fragment)['token'][0]
        health=json.load(urllib.request.urlopen(base+'/api/health'))
        assert health['name']=='no-ide'
        data=json.dumps({'action':'tools.detect'}).encode()
        req=urllib.request.Request(base+'/api/call',data=data,headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
        tools=json.load(urllib.request.urlopen(req,timeout=60))
        assert tools['git']['selected'],tools
        dest=root/'test-results';dest.mkdir(exist_ok=True)
        (dest/('native-'+os.name+'.json')).write_text(json.dumps({'health':health,'tools':tools,'checks':['http','git-discovery']},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Native HTTP and Git detection passed')
    finally:p.terminate();p.wait(timeout=10)
