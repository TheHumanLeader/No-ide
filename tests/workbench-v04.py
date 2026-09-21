"""Real SDK selection and persistent Git/SVN changelist tests on disposable files."""
import json, os, pathlib, platform, shutil, sys
from native_harness import Native, ROOT, cli, wait_for
checks=[]
def check(name,condition=True):
    assert condition,name
    checks.append(name);print('PASS',name,flush=True)

def main():
  with Native() as n:
    tools=n.api('tools.detect');git=tools['git']['selected']['path'];svn=(tools['svn']['selected'] or {}).get('path')
    app=n.root/'application';app.mkdir()
    (app/'app.py').write_text("import os,sys\nprint('PYTHON_OK '+os.environ['FLAG']+' '+sys.argv[1],flush=True)\n",encoding='utf8')
    (app/'server.js').write_text("console.log('NODE_OK '+process.env.FLAG+' '+process.argv[2]);",encoding='utf8')
    (app/'package.json').write_text(json.dumps({'name':'fixture','scripts':{'dev':'node server.js'}}),encoding='utf8')
    (app/'Main.java').write_text('public class Main { public static void main(String[] a) { System.out.println("JAVA_OK "+System.getProperty("java.version")+" "+System.getProperty("custom")+" "+System.getenv("FLAG")+" "+a[0]); }}',encoding='utf8')
    p=n.project(app,'入口验证');pid=p['id']
    d=n.api('project.discover',{'project':pid})
    check('Static discovery finds Python Node npm and Java entries',{'python-file','node-file','npm-script','java-main'}<=set(e['kind'] for e in d['entries']))
    check('Static discovery does not execute project code',not n.api('logs'))
    n.api('project.relative',{'project':pid,'path':str(app.parent)},status=400)
    check('Directory selection cannot escape project root')
    runtimes={}
    for kind,path in [('python',sys.executable),('node',shutil.which('node'))]:
        assert path
        e=n.api('environments.save',{'kind':kind,'path':path,'name':kind+' test','default':True});runtimes[kind]=e
        check(kind+' actual runtime is validated',e['major']>0)
    n.api('environments.save',{'kind':'java','path':sys.executable},status=400);check('Wrong runtime type rejected')
    java=[]
    for envvar in ['TEST_JAVA8','TEST_JAVA17']:
        path=os.environ.get(envvar)
        if path:java.append(n.api('environments.save',{'kind':'java','path':path,'name':envvar}))
    if not java:
        path=shutil.which('java')
        if path:java.append(n.api('environments.save',{'kind':'java','path':path,'name':'Local Java'}))
    if os.environ.get('CI'):assert len(java)==2,'CI must test two real Java versions'
    if len(java)==2:check('Java 8 and Java 17 coexist',sorted(e['major'] for e in java)==[8,17])
    def config(kind,e,env,args,props=None):
        return n.api('config.save',{'project':pid,'config':{'id':'','name':kind+' automatic','cwd':e['cwd'],'environment_id':env['id'],'command':{'program':'auto','args':[]},'env':{'FLAG':'value with spaces'},'watch':[],'launcher':{'kind':e['kind'],'target':e['target'],'sources':e['sources'],'arguments':args,'properties':props or {}}}})
    def launch(c,env=None):
        i=n.api('instance.save',{'project':pid,'instance':{'id':'','name':'runtime test','config_id':c['id'],'environment_id':env['id'] if env else None,'args':[],'env':{}}})
        n.api('run.start',{'project':pid,'instance':i['id']})
        def output():
            lines=[l['text'] for l in n.api('logs') if l['instance']==i['id']]
            return '\n'.join(lines) if any('_OK ' in x for x in lines) else False
        out=wait_for(output,45)
        n.api('run.stop',{'project':pid,'instance':i['id']})
        # Stop is asynchronous; wait for completion before changing shared config.
        wait_for(lambda: next((s for s in n.api('state')['runs'] if s['instance']==i['id']), {}).get('state')=='stopped')
        return out
    for kind,mark in [('python','PYTHON_OK'),('node','NODE_OK')]:
        entry=next(e for e in d['entries'] if e['kind']==kind+'-file')
        c=config(kind,entry,runtimes[kind],['one argument with spaces'])
        check(kind+' generated command runs with intact args and environment',mark+' value with spaces one argument with spaces' in launch(c))
    if java:
        java.sort(key=lambda e:e['major']);entry=next(e for e in d['entries'] if e['kind']=='java-main');c=config('java',entry,java[0],['argument value'],{'custom':'property value'})
        for env in java:
            out=launch(c,env);check('Java '+str(env['major'])+' instance uses selected VM and property',('JAVA_OK '+('1.8.' if env['major']==8 else str(env['major'])+'.')) in out and 'property value value with spaces argument value' in out)
    if os.environ.get('CI'):assert svn,'SVN must be installed in CI'
    for kind in (['git','svn'] if svn else ['git']):
        wc=n.root/(kind+'-wc');wc.mkdir()
        if kind=='git':
            cli(git,'init','-b','main',cwd=wc);cli(git,'config','user.name','No-ide test',cwd=wc);cli(git,'config','user.email','test@example.invalid',cwd=wc)
        else:
            admin=pathlib.Path(svn).with_name('svnadmin.exe' if os.name=='nt' else 'svnadmin')
            if not admin.is_file():admin=shutil.which('svnadmin')
            assert admin
            server=n.root/'svn-server';cli(admin,'create',server);cli(svn,'checkout',server.as_uri(),wc,'--non-interactive')
        for file in ['a.txt','keep.txt']:(wc/file).write_text('old\n',encoding='utf8')
        if kind=='git':cli(git,'add','.',cwd=wc);cli(git,'commit','-m','initial',cwd=wc)
        else:cli(svn,'add','a.txt','keep.txt',cwd=wc);cli(svn,'commit','-m','initial','--non-interactive',cwd=wc)
        repo=n.project(wc,kind+' 分组验证');common={'project':repo['id'],'repo':repo['repos'][0]['id']}
        for f in ['a.txt','keep.txt']:(wc/f).write_text('new '+f+'\n',encoding='utf8')
        g=n.api('vcs.group.save',{**common,'name':'忽略不提交'})['items'][-1]
        n.api('vcs.group.move',{**common,'group':g['id'],'paths':['keep.txt']})
        if kind=='git':cli(git,'add','keep.txt',cwd=wc)
        def prepare(paths,group='default'):return n.api('vcs.prepare',{**common,'operation':'commit','paths':paths,'group':group,'whole_files':True,'message':'only requested group'})
        def execute(plan,status=200):return n.api('vcs.execute',{**common,'token':plan['token'],'confirmed':True},status=status)
        n.api('vcs.prepare',{**common,'operation':'commit','paths':['keep.txt'],'group':'default','whole_files':True,'message':'must reject'},status=400)
        check(kind+' cross-group commit is rejected')
        plan=prepare(['a.txt']);n.api('vcs.group.save',{**common,'group':g['id'],'name':'忽略不提交 · 保留'})
        execute(plan,400);check(kind+' group changes invalidate pending confirmation')
        plan=prepare(['a.txt']);check(kind+' confirmation lists only default group',plan['paths']==['a.txt'] and plan['group']=='default');execute(plan)
        if kind=='git':
            check('Git default commit excludes other group even if staged',cli(git,'show','HEAD:keep.txt',cwd=wc)=='old' and cli(git,'show','HEAD:a.txt',cwd=wc)=='new a.txt')
            check('Git excluded group remains staged',cli(git,'diff','--cached','--name-only',cwd=wc)=='keep.txt')
        else:check('SVN default commit excludes other group',cli(svn,'cat',server.as_uri()+'/keep.txt')=='old' and cli(svn,'cat',server.as_uri()+'/a.txt')=='new a.txt')
        execute(prepare(['keep.txt'],g['id']))
        check(kind+' assignment retained when file becomes clean',not n.api('vcs.status',common)['files'])
        n.stop();n.start();(wc/'keep.txt').write_text('changed again\n',encoding='utf8')
        status=n.api('vcs.status',common);check(kind+' assignment survives real executor restart',next(f for f in status['files'] if f['path']=='keep.txt')['group']==g['id'])
        n.api('vcs.group.delete',{**common,'group':g['id'],'confirmed':True})
        check(kind+' deleting group returns file to default without deleting source',n.api('vcs.status',common)['files'][0]['group']=='default' and (wc/'keep.txt').read_text()=='changed again\n')
    check('Environment registry survives restart',len(n.api('state')['store']['environments'])>=2)

if __name__=='__main__':
    report={'platform':platform.platform(),'checks':checks,'passed':False}
    try:main();report['passed']=True
    except Exception as e:report['error']=str(e);raise
    finally:
        out=ROOT/'test-results';out.mkdir(exist_ok=True);(out/'native-v04.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
