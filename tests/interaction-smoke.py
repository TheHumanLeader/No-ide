"""Browser smoke tests for a generated single-file preview.
Uses the renderer embedded in the tested HTML; does not test a Rust backend.
"""
import argparse
import json
import re
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--html',type=Path,required=True)
parser.add_argument('--output',type=Path,default=Path('test-results'))
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
html=args.html.read_text(encoding='utf-8')
results=[]
errors=[]

def check(name, test):
    test()
    results.append({'test':name,'passed':True})

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1040},device_scale_factor=1)
    page.set_default_timeout(6000)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html,wait_until='load')
    check('Initial render: six services and honest preview label',lambda:(expect(page.locator('.service-row')).to_have_count(6),expect(page.locator('.preview-pill')).to_contain_text('交互预览')))
    page.screenshot(path=str(args.output/'desktop.png'),full_page=True)
    page.locator('.service-search input').fill('Python')
    check('Service filter',lambda:expect(page.locator('.service-row')).to_have_count(1))
    page.locator('.service-search input').fill('')
    page.get_by_role('button',name='模拟代码改动',exact=True).click()
    page.wait_for_timeout(2350)
    check('Successful update increments selected version',lambda:expect(page.locator('.info-grid')).to_contain_text('v4'))
    page.get_by_role('button',name='模拟编译失败',exact=True).click()
    page.wait_for_timeout(1450)
    check('Failed build retains running old version',lambda:(expect(page.locator('.service-row.selected .status')).to_have_text('运行中'),expect(page.locator('.info-grid')).to_contain_text('v4'),expect(page.locator('.feedback.error')).to_be_visible(),expect(page.locator('.issue-row')).to_have_count(1)))
    page.screenshot(path=str(args.output/'error-state.png'),full_page=True)
    page.get_by_role('button',name='复制给 AI',exact=True).click()
    if page.locator('.copy-area').is_visible():
        check('Clipboard fallback includes simulated execution boundary',lambda:expect(page.locator('.copy-area')).to_have_value(re.compile('非真实执行')))
        page.get_by_role('button',name='完成',exact=True).click()
    page.get_by_role('button',name='重试更新',exact=True).click()
    page.wait_for_timeout(2300)
    check('Retry clears issue and publishes next preview version',lambda:(expect(page.locator('.issue-row')).to_have_count(0),expect(page.locator('.info-grid')).to_contain_text('v5')))
    page.get_by_role('button',name='模拟代码改动',exact=True).click()
    page.wait_for_timeout(170)
    page.get_by_role('button',name='停止业务服务',exact=True).click()
    page.wait_for_timeout(2200)
    check('Stop cancels delayed completion; service stays stopped',lambda:expect(page.locator('.service-row.selected .status')).to_have_text('已停止'))
    page.get_by_role('button',name='运行业务服务',exact=True).click()
    page.wait_for_timeout(2300)
    page.get_by_role('switch',name='自动更新',exact=True).uncheck()
    page.get_by_role('button',name='模拟代码改动',exact=True).click()
    check('Automatic updates off queues pending change',lambda:expect(page.locator('.feedback.pending')).to_be_visible())
    page.get_by_role('button',name='应用待处理改动 →',exact=True).click()
    page.wait_for_timeout(2300)
    check('Manual apply consumes pending change',lambda:expect(page.locator('.feedback.pending')).to_have_count(0))
    page.get_by_role('switch',name='自动更新',exact=True).check()
    page.get_by_role('button',name='结果预览',exact=True).click()
    page.get_by_role('button',name='试运行',exact=True).click()
    check('Response explicitly says no network request',lambda:expect(page.locator('.response-code')).to_contain_text('"networkRequestSent": false'))
    page.get_by_role('button',name='运行配置',exact=True).click()
    page.locator('.config-form input').nth(1).fill('java -jar app.jar')
    page.get_by_role('button',name='保存配置',exact=True).click()
    page.get_by_role('button',name='运行配置',exact=True).click()
    check('Configuration saved in session',lambda:expect(page.locator('.config-form input').nth(1)).to_have_value('java -jar app.jar'))
    page.keyboard.press('Control+k')
    page.locator('.command-search input').fill('gateway')
    page.keyboard.press('Enter')
    check('Keyboard service search and navigation',lambda:expect(page.locator('.service-row.selected')).to_contain_text('网关服务'))
    page.locator('.heading-actions').get_by_role('button',name='添加项目',exact=True).click()
    page.locator('.modal form input').nth(0).fill('测试订单服务')
    page.locator('.modal form input').nth(2).fill('C:\\Projects\\orders')
    page.get_by_role('button',name='添加到工作区',exact=False).click()
    check('Add project without accessing filesystem',lambda:(expect(page.locator('.service-row')).to_have_count(7),expect(page.locator('.service-row.selected')).to_contain_text('测试订单服务')))
    page.get_by_role('button',name='设置',exact=True).click()
    page.get_by_role('button',name='星空蓝',exact=True).click()
    check('Theme switch',lambda:expect(page.locator('.no-ide')).to_have_class('no-ide theme-space'))
    page.get_by_role('switch',name='紧凑布局',exact=True).check()
    check('Compact layout',lambda:expect(page.locator('.no-ide')).to_have_class('no-ide compact theme-space'))
    page.get_by_role('button',name='环境与设备',exact=True).click()
    check('Toolchain cards never claim successful detection',lambda:expect(page.locator('.tool-card .status')).to_have_text(['未检测']*4))
    page.get_by_role('button',name='体验设备流程',exact=True).click()
    page.get_by_role('button',name='启用示例设备',exact=True).click()
    check('Android device is clearly only a sample',lambda:expect(page.locator('.device-empty')).to_contain_text('已启用示例 Android 设备'))
    page.get_by_role('button',name='项目管理',exact=True).click()
    check('Project page',lambda:expect(page.locator('.project-card')).to_have_count(7))
    page.get_by_role('button',name='运行记录',exact=True).click()
    check('History receives interactions',lambda:expect(page.locator('.history-row').first).to_be_visible())
    # Start fresh for viewport and initial screenshot coverage.
    for width,height,label in [(1440,1040,'desktop'),(1024,900,'tablet-landscape'),(768,1024,'tablet'),(390,844,'mobile')]:
        pg=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        pg.on('pageerror',lambda e:errors.append(str(e)))
        pg.set_content(html,wait_until='load')
        pg.wait_for_timeout(150)
        dims=pg.evaluate('({viewport:innerWidth,content:document.documentElement.scrollWidth})')
        check(f'{label}: no horizontal page overflow',lambda d=dims:(_ for _ in ()).throw(AssertionError(d)) if d['content']>d['viewport'] else None)
        pg.screenshot(path=str(args.output/f'{label}.png'),full_page=True)
        if label=='mobile':
            pg.get_by_role('button',name='展开导航',exact=True).click()
            pg.get_by_role('button',name='项目管理',exact=True).click()
            check('Mobile navigation',lambda:expect(pg.locator('.projects-page')).to_be_visible())
        pg.close()
    check('No uncaught browser errors',lambda:(_ for _ in ()).throw(AssertionError(errors)) if errors else None)
    mode=page.locator('html').get_attribute('data-renderer')
    browser.close()

report={'renderer':mode,'scope':'UI only; no backend / actual compilation / memory benchmarking','checks':results,'uncaught_errors':errors}
(args.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
