"""Real v0.4 UI + native API. OS folder dialogs are not automated."""
import json, shutil, socket, urllib.request
from playwright.sync_api import sync_playwright, expect
from native_harness import Native, ROOT, cli
checks=[];errors=[]
def check(name):checks.append(name);print('PASS',name,flush=True)
def main():
 with Native() as n:
  root=n.root/'UI project';root.mkdir()
  (root/'server.js').write_text("require('http').createServer((q,r)=>r.end(JSON.stringify({flag:process.env.FLAG,arg:process.argv[2]}))).listen(Number(process.env.PORT),'127.0.0.1');",encoding='utf8')
  for f in ['work.txt','keep.txt']:(root/f).write_text('old\n',encoding='utf8')
  git=shutil.which('git');cli(git,'init','-b','main',cwd=root);cli(git,'config','user.name','UI test',cwd=root);cli(git,'config','user.email','test@example.invalid',cwd=root);cli(git,'add','.',cwd=root);cli(git,'commit','-m','initial',cwd=root)
  env=n.api('environments.save',{'kind':'node','path':shutil.which('node'),'name':'Node UI 验证','default':True})
  project=n.project(root,'界面验收');out=ROOT/'test-results';out.mkdir(exist_ok=True)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=shutil.which('chromium') or None,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1440,'height':1000});page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(n.url);expect(page.locator('.live-real-badge')).to_have_text('真实运行');check('Real local workbench loads')
   page.locator('.nav-item').filter(has_text='运行环境').click();expect(page.locator('.sdk-installed')).to_contain_text('Node UI 验证');check('Runtime library displays saved real environment')
   page.screenshot(path=str(out/'native-v04-environments.png'),full_page=True)
   page.locator('.nav-item').filter(has_text='运行台').click();page.get_by_role('button',name='＋ 运行配置',exact=True).click()
   expect(page.get_by_label('自动运行入口')).to_contain_text('server.js');expect(page.get_by_role('button',name='保存配置',exact=True)).to_be_enabled();check('Project entry is discovered without typing a path')
   expect(page.get_by_label('配置工作目录')).to_have_attribute('readonly','');check('Working directory uses picker rather than required typed path')
   page.get_by_label('配置运行环境').select_option(env['id'])
   page.get_by_role('button',name='＋ 添加程序入参',exact=True).click();page.get_by_label('程序入参值 1',exact=True).fill('one argument with spaces')
   page.get_by_role('button',name='＋ 添加环境变量',exact=True).click();page.get_by_label('环境变量名称 1',exact=True).fill('FLAG');page.get_by_label('环境变量值 1',exact=True).fill('value with spaces');check('Arguments and environment edited with row controls')
   page.screenshot(path=str(out/'native-v04-config.png'),full_page=True)
   page.get_by_role('button',name='保存配置',exact=True).click();expect(page.get_by_label('实例运行环境')).to_be_visible();check('Saving discovered entry proceeds directly to instance creation')
   page.get_by_label('实例运行环境').select_option(env['id']);page.get_by_label('实例名称').fill('实际实例')
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   page.get_by_label('实例端口').fill(str(port));page.get_by_role('button',name='保存实例',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
   page.locator('.live-instance').get_by_role('button',name='运行',exact=True).click();expect(page.locator('.live-instance .status')).to_have_text('运行中')
   result=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}',timeout=10));assert result=={'flag':'value with spaces','arg':'one argument with spaces'},result;check('UI chosen environment and visual fields reach real HTTP app')
   page.locator('.live-instance').get_by_role('button',name='停止',exact=True).click();expect(page.locator('.live-instance .status')).to_have_text('已停止')
   (root/'work.txt').write_text('committed change\n',encoding='utf8');(root/'keep.txt').write_text('kept local\n',encoding='utf8');cli(git,'add','keep.txt',cwd=root)
   page.locator('.nav-item').filter(has_text='代码管理').click();expect(page.locator('.live-file')).to_have_count(2)
   page.get_by_role('button',name='＋ 新建分组',exact=True).click();page.get_by_label('分组名称').fill('忽略不提交');page.get_by_role('button',name='保存分组',exact=True).click();expect(page.get_by_role('button',name='分组 忽略不提交',exact=True)).to_be_visible();check('Custom group created through UI')
   page.get_by_role('checkbox',name='选择 keep.txt',exact=True).check();group=next(g for g in n.api('vcs.status',{'project':project['id'],'repo':project['repos'][0]['id']})['groups'] if g['name']=='忽略不提交')
   page.get_by_label('移动到分组').select_option(group['id']);page.get_by_role('button',name='移动选中文件',exact=True).click();expect(page.locator('.live-file')).to_have_count(1);expect(page.locator('.live-file')).to_contain_text('work.txt');check('Batch move removes protected file from default group')
   page.locator('.live-file button').click();expect(page.locator('.live-diff-body')).to_contain_text('+committed change')
   page.screenshot(path=str(out/'native-v04-groups.png'),full_page=True)
   page.locator('.live-commit textarea').fill('default group UI commit');page.get_by_role('button',name='检查并提交整个「默认」（1 项）',exact=True).click();expect(page.locator('.live-confirm-files')).to_have_text('work.txt');check('Commit review only includes current group')
   page.get_by_role('button',name='确认执行',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
   assert cli(git,'show','HEAD:keep.txt',cwd=root)=='old';assert cli(git,'diff','--cached','--name-only',cwd=root)=='keep.txt';check('Real Git commit does not include protected staged file')
   page.reload();page.locator('.nav-item').filter(has_text='代码管理').click();page.get_by_role('button',name='分组 忽略不提交',exact=True).click();expect(page.locator('.live-file')).to_contain_text('keep.txt');check('File grouping survives browser reload')
   page.locator('.live-file').drag_to(page.get_by_role('button',name='分组 默认',exact=True));page.get_by_role('button',name='分组 默认',exact=True).click();expect(page.locator('.live-file')).to_contain_text('keep.txt');check('Drag and drop persists a group move')
   page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth');check('Group view has no horizontal page overflow on mobile')
   page.locator('.nav-item').filter(has_text='运行环境').click();assert page.evaluate('document.documentElement.scrollWidth <= innerWidth');check('Runtime settings have no mobile page overflow')
   assert not errors,errors;check('No uncaught browser errors');browser.close()

if __name__=='__main__':
 report={'checks':checks,'page_errors':errors,'passed':False,'scope':'Real Quasar build with Rust API; no OS picker automation'}
 try:main();report['passed']=True
 except Exception as e:report['error']=str(e);raise
 finally:
  out=ROOT/'test-results';out.mkdir(exist_ok=True);(out/'native-v04-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
