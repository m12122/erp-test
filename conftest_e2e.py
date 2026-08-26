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


def ensure_product_a_exists(page):
    # 确保产品A存在
    page.locator("div").filter(has_text=re.compile(r"^产品管理$")).click()
    page.get_by_role("menuitem", name="产品信息").click()
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_selector("button:has-text('新增产品')", timeout=15000)

    # 额外等待几秒让数据完全渲染
    page.wait_for_timeout(2000)

    if page.locator("tr:has-text('产品A')").count() == 0:
        page.get_by_role("button", name="新增产品").click()
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill('input[name="name"]', "产品A")
        page.click('button:has-text("保存")')
        page.wait_for_selector("text=产品列表", timeout=5000)
        print("✅ 产品A 创建成功")
    else:
        print("✅ 产品A 已存在")


# def set_product_stock(page, quantity=10):
#     # 设置产品A的库存
#     page.locator("div").filter(has_text=re.compile(r"^产品管理$")).click()
#     page.get_by_role("menuitem", name="产品信息").click()
#     page.wait_for_load_state("networkidle", timeout=15000)
#     page.wait_for_selector("button:has-text('新增产品')", timeout=15000)

#     row = page.locator("tr:has-text('产品A')")
#     row.locator("button:has-text('编辑')").click()
#     page.wait_for_selector(".ant-modal", state="attached", timeout=15000)
#     page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton").fill(str(quantity))
#     page.get_by_role("button", name="确 定").click()
#     page.wait_for_selector(".ant-modal", state="hidden", timeout=15000)
#     print(f"✅ 产品A 库存设置为{quantity}")

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
    """执行一次基础数据准备"""
    ensure_product_a_exists(page)
    # set_product_stock(page, 10)
    ensure_basedata_exists(page)
    ensure_accounts_exist(page)
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
