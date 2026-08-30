import pytest
import re
from playwright.sync_api import sync_playwright

BASE_URL = "http://8.156.85.50:8080"
USERNAME = "管理员"
PASSWORD = "123456"


def login(page):
    page.goto(f"{BASE_URL}/#/yindao")
    page.wait_for_selector("button:has-text('立即开始')", timeout=30000)
    page.get_by_role("button", name="立即开始").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.reload()
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_selector("input[type=\"text\"]", timeout=15000)
    page.locator("input[type=\"text\"]").fill(USERNAME)
    page.locator("input[type=\"password\"]").fill(PASSWORD)
    page.get_by_role("button", name="登 录").click()
    page.wait_for_selector("text=客户管理", timeout=30000)
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    print("✅ 登录成功")


def ensure_category_exists(page):
    # 确保产品分类存在，如果不存在则创建
    page.locator("div").filter(has_text=re.compile(r"^产品管理$")).click()
    page.get_by_role("menuitem", name="产品分类").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_selector("button:has-text('新增分类')", timeout=15000)

    # 额外等待几秒让数据完全渲染
    page.wait_for_timeout(2000)

    if page.locator("tr:has-text('默认分类')").count() == 0:
        # 点击新增分类
        page.get_by_role("button", name="图标: plus 新增分类").click()
        page.wait_for_selector(".ant-modal", timeout=10000)
        # 填写分类名称
        page.get_by_role("textbox").nth(1).click()
        page.get_by_role("textbox").nth(1).fill("默认分类")
        page.get_by_role("button", name="确 定").click()
        print("✅ 默认分类 创建成功")
    else:
        print("✅ 默认分类 已存在")


def ensure_basedata_exists(page):
    page.locator("div").filter(has_text=re.compile(r"^基础数据$")).click()
    # 确保默认客户存在
    page.get_by_role("menuitem", name="客户管理").click()
    page.wait_for_load_state("networkidle", timeout=10000)
    page.wait_for_selector("button:has-text('新增客户')", timeout=10000)

    # 额外等待几秒让数据完全渲染
    page.wait_for_timeout(2000)

    if page.locator("tr:has-text('默认客户')").count() == 0:
        page.get_by_role("button", name="新增客户").click()
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill('input[name="name"]', "默认客户")
        page.click('button:has-text("保存")')
        page.wait_for_selector("text=客户列表", timeout=5000)
        print("✅ 默认客户 创建成功")
    else:
        print("✅ 默认客户 已存在")

    # 确保默认供应商存在
    page.get_by_role("menuitem", name="供应商管理").click()
    page.wait_for_load_state("networkidle", timeout=10000)
    page.wait_for_selector("button:has-text('新增供应商')", timeout=10000)

    # 额外等待几秒让数据完全渲染
    page.wait_for_timeout(2000)

    if page.locator("tr:has-text('默认供应商')").count() == 0:
        page.get_by_role("button", name="新增供应商").click()
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill('input[name="name"]', "默认供应商")
        page.click('button:has-text("保存")')
        page.wait_for_selector("text=供应商列表", timeout=5000)
        print("✅ 默认供应商 创建成功")
    else:
        print("✅ 默认供应商 已存在")

    # 确保默认仓库存在
    page.get_by_role("menuitem", name="仓库管理").click()
    page.wait_for_load_state("networkidle", timeout=10000)
    page.wait_for_selector("button:has-text('新增仓库')", timeout=10000)

    # 额外等待几秒让数据完全渲染
    page.wait_for_timeout(2000)

    if page.locator("tr:has-text('默认仓库')").count() == 0:
        page.get_by_role("button", name="新增仓库").click()
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill('input[name="name"]', "默认仓库")
        page.click('button:has-text("保存")')
        page.wait_for_selector("text=仓库列表", timeout=5000)
        print("✅ 默认仓库 创建成功")
    else:
        print("✅ 默认仓库 已存在")


def ensure_purchase_order_exists(page):
    # 确保存在至少一个采购单，如果没有则创建一个
    # 进入采购记录
    page.locator("div").filter(has_text=re.compile(r"^采购管理$")).click()
    page.get_by_role("menuitem", name="采购记录").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_selector("table", timeout=15000)

    page.wait_for_timeout(2000)

    # 检查表格中是否有数据（至少一行）
    rows = page.locator("table tbody tr")
    if rows.count() > 0:
        print("✅ 采购单 已存在")
        return

    # ---------- 没有采购单，创建一条 ----------
    print("⚠️ 未找到采购单，正在创建...")

    # 进入采购开单
    page.locator("div").filter(has_text=re.compile(r"^采购管理$")).click()
    page.get_by_role("menuitem", name="采购开单").click()
    page.wait_for_load_state("networkidle", timeout=15000)

    # 选择供应商（默认供应商）
    page.locator(".ant-select-selection__rendered").first.click()
    page.get_by_role("option", name="默认供应商").click()

    # 选择仓库（默认仓库）
    page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
    page.get_by_role("option", name="默认仓库").click()

    # 选择经手人（管理员）
    page.locator("div:nth-child(4) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
    page.get_by_role("option", name="管理员").click()

    # 选择日期（今天）
    from datetime import datetime
    today_day = datetime.now().day
    page.get_by_role("textbox", name="请选择日期").click()
    page.get_by_text(str(today_day)).nth(1).click()

    # 添加产品
    page.get_by_role("button", name="添加产品").click()
    page.locator(".ant-modal tr:has-text('产品A')").last.get_by_role("button", name="选 择").click()

    # 填写数量50、单价100、税率0%
    spinbuttons = page.locator("table tbody tr:first-child [role='spinbutton']")
    spinbuttons.nth(0).fill("50")   # 数量
    spinbuttons.nth(1).fill("100")  # 单价
    spinbuttons.nth(2).fill("0")    # 税率

    # 保存
    page.get_by_role("button", name="保 存").click()
    page.get_by_role("button", name="确 定").click()

    # 等待保存成功（跳转到采购记录列表）
    page.wait_for_url("**/#/purchasing/purchase_record", timeout=15000)
    page.wait_for_selector(".ant-message-success", timeout=10000)
    print("✅ 采购单 创建成功")

def ensure_sales_order_exists(page):
    # 确保存在至少一个销售单，如果没有则创建一个
    # 进入销售记录
    page.locator("div").filter(has_text=re.compile(r"^销售管理$")).click()
    page.get_by_role("menuitem", name="销售记录").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_selector("table", timeout=15000)

    page.wait_for_timeout(2000)

    # 检查是否有销售单
    if page.locator("table tbody tr").count() > 0:
        print("✅ 销售单 已存在")
        return

    # ---------- 没有销售单，创建一条 ----------
    print("⚠️ 未找到销售单，正在创建...")

    # 进入销售开单
    page.locator("div").filter(has_text=re.compile(r"^销售管理$")).click()
    page.get_by_role("menuitem", name="销售开单").click()
    page.wait_for_load_state("networkidle", timeout=15000)

    # 选择仓库、客户、经手人
    page.locator(".ant-select-selection__rendered").first.click()
    page.get_by_role("option", name="默认仓库").click()
    page.locator(".ant-select-selection__rendered").nth(1).click()
    page.get_by_role("option", name="默认客户").click()
    page.locator(".ant-select-selection__rendered").nth(2).click()
    page.get_by_role("option", name="管理员").click()

    # 选择日期（今天）
    from datetime import datetime
    today_day = datetime.now().day
    page.get_by_role("textbox", name="请选择日期").click()
    page.get_by_text(str(today_day)).nth(1).click()

    # 添加产品（选择第一个产品）
    page.get_by_role("button", name="添加产品").click()
    page.locator(".ant-modal tr:has-text('产品A')").first.get_by_role("button", name="选 择").click()

    # 填写数量20、单价150、税率0%
    spinbuttons = page.locator("table tbody tr:first-child [role='spinbutton']")
    spinbuttons.nth(0).fill("20")
    spinbuttons.nth(1).fill("150")
    spinbuttons.nth(2).fill("0")

    # 保存
    page.get_by_role("button", name="保 存").click()
    page.get_by_role("button", name="确 定").click()

    # 等待保存成功
    page.wait_for_url("**/#/sale/sale_record", timeout=15000)
    page.wait_for_selector(".ant-message-success", timeout=10000)
    print("✅ 销售单 创建成功")


def ensure_accounts_exist(page):
    # 确保微信账户和银行账户存在，并设置初始余额
    page.locator("div").filter(has_text=re.compile(r"^基础数据$")).click()
    page.get_by_role("menuitem", name="结算账户").click()
    page.wait_for_load_state("networkidle", timeout=10000)
    page.wait_for_selector("button:has-text('新增结算账户')", timeout=10000)

    # 额外等待几秒让数据完全渲染
    page.wait_for_timeout(2000)

    # 创建微信账户
    if page.locator("tr:has-text('微信账户')").count() == 0:
        page.get_by_role("button", name="新增结算账户").click()
        page.wait_for_selector(".ant-modal", timeout=10000)
        page.wait_for_timeout(500)
        name_input = page.locator(".ant-modal input[type='text']").first
        name_input.click()
        name_input.fill("微信账户")
        page.locator(".ant-modal .ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="微信钱包").click()
        page.get_by_role("spinbutton").fill("10000")
        page.get_by_role("button", name="确 定").click()
        print("✅ 微信账户 创建成功")
    else:
        print("✅ 微信账户 已存在")


    # 创建银行账户
    if page.locator("tr:has-text('银行账户')").count() == 0:
        page.get_by_role("button", name="新增结算账户").click()
        page.wait_for_selector(".ant-modal", timeout=10000)
        page.wait_for_timeout(500)
        name_input = page.locator(".ant-modal input[type='text']").first
        name_input.click()
        name_input.fill("银行账户")
        page.locator(".ant-modal .ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="银行账户").click()
        page.get_by_role("spinbutton").fill("5000")
        page.get_by_role("button", name="确 定").click()
        print("✅ 银行账户 创建成功")
    else:
        print("✅ 银行账户 已存在")



def prepare_base_data(page):
    # 执行一次基础数据准备
    ensure_category_exists(page)
    ensure_basedata_exists(page)
    ensure_accounts_exist(page)
    ensure_purchase_order_exists(page)
    ensure_sales_order_exists(page)
    print("✅ 所有基础数据准备完成")


@pytest.fixture(scope="session")
def logged_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()
        login(page)

        # 登录成功后准备基础数据
        prepare_base_data(page)

        yield page
        context.close()
        browser.close()