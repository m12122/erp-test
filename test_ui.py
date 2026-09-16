import re
import pytest
from playwright.sync_api import expect, sync_playwright, Page
# 从 conftest 中导入登录所需的常量
from conftest import BASE_URL, USERNAME, PASSWORD

# 全局变量用于传递单号
purchase_order_no = None
sales_order_no = None

from datetime import datetime
today_day = datetime.now().day


# 登录相关用例
class TestLogin:

    def test_login_page_rendering(self):
        # TC-UI-034 用户登录-页面交互验证
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(f"{BASE_URL}/#/yindao")
            
            # 点击“立即开始”
            page.wait_for_selector("button:has-text('立即开始')", timeout=30000)
            page.get_by_role("button", name="立即开始").click()
            page.wait_for_load_state("networkidle")
            page.reload()  # 刷新加载登录框
            page.wait_for_selector("input[type='text']", timeout=15000)

            # 断言：用户名、密码输入框和登录按钮可见且渲染正确
            expect(page.locator("input[type='text']")).to_be_visible()
            expect(page.locator("input[type='password']")).to_be_visible()
            expect(page.get_by_role("button", name="登 录")).to_be_visible()

            page.locator("input[type='text']").fill(USERNAME)
            page.locator("input[type='password']").fill(PASSWORD)
            page.get_by_role("button", name="登 录").click()

            # 断言：登录成功后提示“登录成功”，跳转到客户管理页面，且用户名显示正确
            expect(page.get_by_text("登录成功", exact=True)).to_be_visible(timeout=3000)
            page.wait_for_url("**/basicData/client", timeout=10000)
            expect(page).to_have_url("http://8.156.85.50:8080/#/basicData/client")
            expect(page.locator("body")).to_contain_text("管理员")
            
            browser.close()

    def test_login_wrong_password(self):
        # TC-UI-035 用户登录-错误密码反馈验证
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(f"{BASE_URL}/#/yindao")
            
            page.wait_for_selector("button:has-text('立即开始')", timeout=30000)
            page.get_by_role("button", name="立即开始").click()
            page.wait_for_load_state("networkidle")
            page.reload()
            page.wait_for_selector("input[type='text']", timeout=15000)

            # 输入正确用户名，错误密码
            page.locator("input[type='text']").fill(USERNAME)
            page.locator("input[type='password']").fill("wrong_password")
            page.get_by_role("button", name="登 录").click()

            # 断言1：出现错误提示“密码错误”
            error = page.locator("text=密码错误")
            expect(error).to_be_visible()
            
            # 断言2：停留在登录页（未跳转到后台首页）
            assert "yindao" in page.url or "login" in page.url, "登录失败但页面跳转了"
            
            browser.close()


@pytest.mark.usefixtures("logged_page")
class TestUIFunctional:

    # ========== TC-UI-001 产品创建-页面交互验证 ==========
    def test_product_create_page_interaction(self, logged_page):
        page = logged_page

        # 进入产品列表
        page.locator("div").filter(has_text=re.compile(r"^产品管理$")).click()
        page.get_by_role("menuitem", name="产品信息").click()
        page.wait_for_load_state("networkidle")

        # 点击新增产品
        page.get_by_role("button", name="图标: plus 新增产品").click()
        page.wait_for_selector(".ant-modal", timeout=10000)

        # 断言1：产品名称输入框可见
        expect(page.get_by_role("textbox").nth(2)).to_be_visible()

        # 断言2：分类下拉框可展开且加载选项
        expect(page.locator(".ant-select-selection__rendered").first).to_be_visible()
        page.locator(".ant-select-selection__rendered").first.click()
        page.wait_for_selector(".ant-select-dropdown-menu-item", timeout=5000)
        options = page.locator(".ant-select-dropdown-menu-item")
        assert options.count() > 0, "分类下拉框无选项"
        options.first.click()

        # 填写其他字段并保存
        page.get_by_role("textbox").nth(3).fill("产品A")
        page.get_by_role("spinbutton").first.fill("100")
        page.get_by_role("spinbutton").nth(1).fill("150")
        page.get_by_role("button", name="确 定").click()

        # 断言：保存成功提示，并显示
        page.wait_for_selector(".ant-message-success", timeout=10000)
        expect(page.locator(".ant-message-success")).to_be_visible()
        page.wait_for_selector(f"tr:has-text('产品A')", timeout=10000)
        
    # ========== TC-UI-003 产品编辑-页面交互验证 ==========
    def test_product_edit_flow(self, logged_page):
        page = logged_page

        page.locator("div").filter(has_text=re.compile(r"^产品管理$")).click()
        page.get_by_role("menuitem", name="产品信息").click()
        page.wait_for_load_state("networkidle")

        row = page.locator("tr:has-text('产品A')").last

        product_code = row.locator("td:nth-child(2)").text_content().strip()
        print(f"正在编辑的产品编号: {product_code}")

        row.get_by_role("button", name="图标: edit 编辑").click()
        page.wait_for_selector(".ant-modal", timeout=10000)

        # 断言：编辑弹窗中字段回填为产品A的值
        name_input = page.get_by_role("textbox").nth(3)
        expect(name_input).to_have_value("产品A")

        # 修改零售价为200
        page.get_by_role("spinbutton").nth(1).fill("200") 
        page.get_by_role("button", name="确 定").click()

        page.wait_for_selector(".ant-message-success", timeout=10000)
        expect(page.locator(".ant-message-success")).to_be_visible()
        page.wait_for_selector("tr:has-text('产品A')", timeout=15000)

        page.wait_for_selector(f"tr:has-text('{product_code}')", timeout=15000)
        page.wait_for_timeout(2000)
        
        headers = page.locator("table thead th").all_text_contents()
        price_col_index = None
        for i, h in enumerate(headers, start=1):
            if "零售价" in h:
                price_col_index = i
                break
        assert price_col_index is not None, "未找到零售价列"

        target_row = page.locator(f"tr:has-text('{product_code}')")
        new_price = target_row.locator(f"td:nth-child({price_col_index})").text_content().strip()
        assert new_price == "200", f"产品A的零售价预期为200，实际为{new_price}"

    # ========== TC-UI-005 产品创建-前端必填校验验证 ==========
    def test_product_create_required_validation(self, logged_page):
        page = logged_page

        page.locator("div").filter(has_text=re.compile(r"^产品管理$")).click()
        page.get_by_role("menuitem", name="产品信息").click()
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="图标: plus 新增产品").click()
        page.wait_for_selector(".ant-modal", timeout=10000)

        page.locator(".ant-select-selection__rendered").first.click()
        page.wait_for_selector(".ant-select-dropdown-menu-item", timeout=5000)
        page.locator(".ant-select-dropdown-menu-item").first.click()
        page.get_by_role("spinbutton").first.fill("100")
        page.get_by_role("spinbutton").nth(1).fill("150")
        page.get_by_role("button", name="确 定").click()

        error_msg = page.get_by_text("请输入产品名称")
        expect(error_msg).to_be_visible()
        assert page.locator(".ant-modal").is_visible(), "提交后弹窗意外关闭"

        page.keyboard.press("Escape")
        page.wait_for_selector(".ant-modal", state="hidden", timeout=5000)
        print("✅ 必填校验验证通过，弹窗已关闭")


    # ========== TC-UI-006 采购单详情-查看验证 ==========
    def test_purchase_order_detail_view(self, logged_page):
        page = logged_page

        # 进入采购记录
        page.locator("div").filter(has_text=re.compile(r"^采购管理$")).click()
        page.get_by_role("menuitem", name="采购记录").click()
        page.wait_for_load_state("networkidle")

        page.wait_for_timeout(2000)

        # 点击第一条记录的"详情"按钮
        page.get_by_role("button", name="详 情").first.click()
        page.wait_for_load_state("networkidle")

        # 断言：详情页显示供应商、仓库、产品明细、总金额
        expect(page.get_by_role("rowheader", name="供应商")).to_be_visible()
        expect(page.get_by_role("cell", name="默认供应商")).to_be_visible()
        expect(page.get_by_role("rowheader", name="仓库")).to_be_visible()
        expect(page.get_by_role("cell", name="默认仓库")).to_be_visible()
        expect(page.get_by_role("cell", name="产品A")).to_be_visible()
        # 验证总金额存在
        expect(page.get_by_role("cell", name="5000.00")).to_be_visible()

    # ========== TC-UI-007 采购开单-税率修改税额自动计算验证 ==========
    def test_purchase_order_tax_calculation(self, logged_page):
        page = logged_page

        # 进入采购开单
        page.locator("div").filter(has_text=re.compile(r"^采购管理$")).click()
        page.get_by_role("menuitem", name="采购开单").click()
        page.wait_for_load_state("networkidle")

        # 选择供应商、仓库、经手人
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认供应商").click()
        page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="默认仓库").click()
        page.locator("div:nth-child(4) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 添加产品
        page.get_by_role("button", name="添加产品").click()
        page.locator(".ant-modal tr:has-text('产品A')").last.get_by_role("button", name="选 择").click()

        # 填写数量50、单价100、税率13%
        spinbuttons = page.locator("table tbody tr:first-child [role='spinbutton']")
        spinbuttons.nth(0).fill("50")   # 数量
        spinbuttons.nth(1).fill("100")  # 单价
        spinbuttons.nth(2).fill("13")   # 税率

        page.wait_for_timeout(500)
        # 断言：合计金额自动变为5650（税额650）
        expect(page.get_by_text("5650").first).to_be_visible()

    # ========== TC-UI-008/009 采购开单数量为0/负数校验（合并） ==========
    @pytest.mark.parametrize("invalid_value", [
        (0, "数量为0"),
        (-5, "数量为负数"),
    ])
    def test_purchase_order_invalid_quantity_validation(self, logged_page, invalid_value):
        invalid_number, description = invalid_value
        page = logged_page

        # 进入采购开单
        page.locator("div").filter(has_text=re.compile(r"^采购管理$")).click()
        page.get_by_role("menuitem", name="采购开单").click()
        page.wait_for_load_state("networkidle")

        # 选择供应商、仓库、经手人
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认供应商").click()

        page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="默认仓库").click()

        page.locator("div:nth-child(4) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 添加产品
        page.get_by_role("button", name="添加产品").click()
        page.locator(".ant-modal tr:has-text('产品A')").last.get_by_role("button", name="选 择").click()

        # 根据参数填写数量（0 或 -5）
        spinbuttons = page.locator("table tbody tr:first-child [role='spinbutton']")
        spinbuttons.nth(0).fill(str(invalid_number))  # 数量（0或-5）
        spinbuttons.nth(1).fill("100")                # 单价
        spinbuttons.nth(2).fill("0")                  # 税率
        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        # 断言：出现错误提示（实际系统提示为"采购单价和采购数量必填"）
        error_msg = page.get_by_text("采购单价和采购数量必填").first
        expect(error_msg).to_be_visible()
        print(f"✅ {description}校验通过")




    # ========== TC-UI-010 销售单详情-查看验证 ==========
    def test_sales_order_detail_view(self, logged_page):
        page = logged_page

        # 进入销售记录
        page.locator("div").filter(has_text=re.compile(r"^销售管理$")).click()
        page.get_by_role("menuitem", name="销售记录").click()
        page.wait_for_load_state("networkidle")

        # 点击第一条记录的"详 情"按钮（根据采购模块经验，详情按钮名称可能是"详 情"）
        page.get_by_role("button", name="详 情").first.click()
        page.wait_for_load_state("networkidle")

        # 断言：详情页显示客户、仓库、产品明细、总金额
        expect(page.get_by_role("rowheader", name="客户")).to_be_visible()
        expect(page.get_by_role("cell", name="默认客户")).to_be_visible()
        expect(page.get_by_role("rowheader", name="仓库")).to_be_visible()
        expect(page.get_by_role("cell", name="默认仓库")).to_be_visible()
        expect(page.get_by_role("cell", name="产品A")).to_be_visible()
        # 验证总金额存在
        expect(page.get_by_role("cell", name=re.compile(r"\d+\.\d{2}")).first).to_be_visible()


    # ========== TC-UI-011 销售开单-税率修改税额自动计算验证 ==========
    def test_sales_order_tax_calculation(self, logged_page):
        page = logged_page

        # 进入销售开单
        page.locator("div").filter(has_text=re.compile(r"^销售管理$")).click()
        page.get_by_role("menuitem", name="销售开单").click()
        page.wait_for_load_state("networkidle")

        # 选择仓库、客户、经手人
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认仓库").click()

        page.locator(".ant-select-selection__rendered").nth(1).click()
        page.get_by_role("option", name="默认客户").click()

        page.locator(".ant-select-selection__rendered").nth(2).click()
        page.get_by_role("option", name="管理员").click()

        # 选择日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 添加产品
        page.get_by_role("button", name="添加产品").click()
        page.locator(".ant-modal tr:has-text('产品A')").last.get_by_role("button", name="选 择").click()

        # 填写数量20、单价150、税率13%
        spinbuttons = page.locator("table tbody tr:first-child [role='spinbutton']")
        spinbuttons.nth(0).fill("20")   # 数量
        spinbuttons.nth(1).fill("150")  # 单价
        spinbuttons.nth(2).fill("13")   # 税率

        page.wait_for_timeout(500)
        # 断言：合计金额自动变为3390
        expect(page.get_by_role("cell", name="3390").first).to_be_visible()


    # ========== TC-UI-017 付款-正常付款验证 ==========
    def test_payment_normal(self, logged_page):
        page = logged_page

        # 进入财务管理→付款
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="付款").click()
        page.wait_for_load_state("networkidle")

        # 点击新增付款单
        page.get_by_role("button", name="图标: plus 新增付款单").click()
        page.wait_for_load_state("networkidle")

        # 断言1：页面显示供应商下拉框、经手人下拉框、处理日期选择器
        expect(page.locator(".ant-select-selection__rendered").first).to_be_visible()

        # 选择供应商
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认供应商").click()

        # 选择经手人
        page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择处理日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 选择付款账户（微信账户）
        page.locator("div > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="微信账户").click()

        # 断言2：金额输入框可见（spinbutton）
        expect(page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton")).to_be_visible()

        # 输入金额1000
        page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton").fill("1000")

        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        # 断言：付款单创建成功（成功提示出现）
        page.wait_for_selector(".ant-message-success", timeout=10000)
        expect(page.locator(".ant-message-success")).to_be_visible()
        print("✅ 付款单创建成功")


    # ========== TC-UI-018 付款-金额为0校验 ==========
    def test_payment_zero_amount_validation(self, logged_page):
        page = logged_page

        # 进入财务管理→付款
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="付款").click()
        page.wait_for_load_state("networkidle")

        # 点击新增付款单
        page.get_by_role("button", name="图标: plus 新增付款单").click()
        page.wait_for_load_state("networkidle")

        # 选择供应商
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认供应商").click()

        # 选择经手人
        page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择处理日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 选择付款账户
        page.locator("div > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="微信账户").click()

        # 输入金额0
        page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton").fill("0")

        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        # 断言：出现错误提示"付款金额小于或等于零"
        error_msg = page.get_by_text("付款金额小于或等于零")
        expect(error_msg).to_be_visible()
        print("✅ 付款金额为0校验通过")


    # ========== TC-UI-019 收款-正常收款验证 ==========
    def test_collection_normal(self, logged_page):
        page = logged_page

        # 进入财务管理→收款
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="收款").click()
        page.wait_for_load_state("networkidle")

        # 点击新增收款单
        page.get_by_role("button", name="图标: plus 新增收款单").click()
        page.wait_for_load_state("networkidle")

        # 断言1：页面显示客户下拉框、经手人下拉框、处理日期选择器
        expect(page.locator(".ant-select-selection__rendered").first).to_be_visible()

        # 选择客户
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认客户").click()

        # 选择经手人
        page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择处理日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 选择收款账户（微信账户）
        page.locator("div > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="微信账户").click()

        # 断言2：金额输入框可见（spinbutton）
        expect(page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton")).to_be_visible()

        # 输入金额1000
        page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton").fill("1000")

        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        # 断言：收款单创建成功
        page.wait_for_selector(".ant-message-success", timeout=10000)
        expect(page.locator(".ant-message-success")).to_be_visible()
        print("✅ 收款单创建成功")


    # ========== TC-UI-020 收款-金额为0校验 ==========
    def test_collection_zero_amount_validation(self, logged_page):
        page = logged_page

        # 进入财务管理→收款
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="收款").click()
        page.wait_for_load_state("networkidle")

        # 点击新增收款单
        page.get_by_role("button", name="图标: plus 新增收款单").click()
        page.wait_for_load_state("networkidle")

        # 选择客户
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认客户").click()

        # 选择经手人
        page.locator("div:nth-child(3) > .ant-row > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择处理日期
        page.get_by_role("textbox", name="请选择日期").click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 选择收款账户
        page.locator("div > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="微信账户").click()

        # 输入金额0
        page.get_by_role("cell", name="Increase Value Decrease Value").get_by_role("spinbutton").fill("0")

        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        # 断言：出现错误提示"收款金额小于或等于零"
        error_msg = page.get_by_text("收款金额小于或等于零")
        expect(error_msg).to_be_visible()
        print("✅ 收款金额为0校验通过")    


    # ========== TC-UI-024 账户转账-余额不足前端提示验证 ==========
    def test_transfer_insufficient_balance(self, logged_page):
        page = logged_page

        # 进入财务管理→账户转账
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="账户转账").click()
        page.wait_for_load_state("networkidle")

        # 点击新增账户转账（跳转到创建页）
        page.get_by_role("button", name="图标: plus 新增账户转账").click()
        page.wait_for_load_state("networkidle")

        # 选择转出账户（微信账户）
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="微信账户").click()

        # 选择转出日期
        page.get_by_role("textbox", name="请选择日期").first.click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 选择转入账户（银行账户）
        page.locator("div:nth-child(3) > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="银行账户").click()

        # 选择转入日期
        page.get_by_role("textbox", name="请选择日期").nth(1).click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 输入金额20000
        page.get_by_role("spinbutton").first.fill("20000")

        # 选择经手人
        page.locator("div:nth-child(8) > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 选择处理日期
        page.get_by_role("textbox", name="请选择日期").nth(2).click()
        page.get_by_text(str(today_day)).nth(1).click()

        # 点击确定
        page.get_by_role("button", name="确 定").click()

        # 断言：出现余额不足提示
        error_msg = page.get_by_text("结算账户[微信账户]余额不足")
        expect(error_msg).to_be_visible()
        page.get_by_role("button", name="Close").click()
        page.wait_for_selector(".ant-modal", state="hidden", timeout=5000)
        print("✅ 账户转账余额不足校验通过")



    # ========== TC-UI-044 角色管理-页面加载验证 ==========
    def test_role_management_page_load(self, logged_page):
        page = logged_page

        # 进入角色管理页
        page.locator("div").filter(has_text=re.compile(r"^系统管理$")).click()
        page.get_by_role("menuitem", name="角色管理").click()
        page.wait_for_load_state("networkidle")

        # 断言：角色列表表格可见
        expect(page.locator("table")).to_be_visible()
        # 断言："新增角色"按钮可见
        expect(page.get_by_role("button", name="图标: plus 新增角色")).to_be_visible()

    # ========== TC-UI-045 角色管理-权限树展示验证 ==========
    def test_role_permission_tree_display(self, logged_page):
        page = logged_page

        # 进入角色管理页
        page.locator("div").filter(has_text=re.compile(r"^系统管理$")).click()
        page.get_by_role("menuitem", name="角色管理").click()
        page.wait_for_load_state("networkidle")

        # 点击"新增角色"打开弹窗（权限列表直接展示）
        page.get_by_role("button", name="图标: plus 新增角色").click()
        page.wait_for_selector(".ant-modal", timeout=5000)

        # 验证权限树一级模块可见（根据截图）
        expected_modules = ["数据看板", "报表统计", "采购管理", "销售管理", "库存管理", "往来管理"]
        for module in expected_modules:
            # 在弹窗中查找包含模块文本的元素
            expect(page.locator(f".ant-modal :has-text('{module}')").first).to_be_visible()

        # 验证部分子权限可见（采购管理下的采购订单、采购退货）
        expect(page.locator(".ant-modal :has-text('采购订单')").first).to_be_visible()
        expect(page.locator(".ant-modal :has-text('采购退货')").first).to_be_visible()

        # 验证销售管理下的销售订单、销售退货
        expect(page.locator(".ant-modal :has-text('销售订单')").first).to_be_visible()
        expect(page.locator(".ant-modal :has-text('销售退货')").first).to_be_visible()

        # 关闭弹窗（取消）
        page.get_by_role("button", name="取 消").click()
        page.wait_for_selector(".ant-modal", state="hidden", timeout=3000)

    # ========== TC-UI-046 角色管理-新增角色权限分配验证 ==========
    def test_role_create_with_permission(self, logged_page):
        page = logged_page

        # 进入角色管理页
        page.locator("div").filter(has_text=re.compile(r"^系统管理$")).click()
        page.get_by_role("menuitem", name="角色管理").click()
        page.wait_for_load_state("networkidle")

        # 点击"新增角色"
        page.get_by_role("button", name="图标: plus 新增角色").click()
        page.wait_for_selector(".ant-modal", timeout=5000)

        # 填写角色名称（录制中的第2个textbox）
        page.get_by_role("textbox").nth(1).fill("测试角色")

        # 勾选"销售订单"权限
        page.get_by_role("checkbox", name="销售订单").check()

        # 点击"确定"保存
        page.get_by_role("button", name="确 定").click()

        # 等待保存成功提示
        page.wait_for_selector(".ant-message-success", timeout=5000)
        expect(page.locator(".ant-message-success")).to_be_visible()

        # 验证列表显示新增角色
        expect(page.locator("tr:has-text('测试角色')")).to_be_visible()

    # ========== TC-UI-047 角色管理-分配角色权限验证 ==========
    def test_role_assign_permission(self, logged_page):
        page = logged_page

        # 进入角色管理页
        page.locator("div").filter(has_text=re.compile(r"^系统管理$")).click()
        page.get_by_role("menuitem", name="角色管理").click()
        page.wait_for_load_state("networkidle")

        # 确保测试角色存在（由 TC-UI-046 创建）
        row = page.locator("tr:has-text('测试角色')")
        expect(row).to_be_visible()

        # 点击"编辑"
        row.get_by_role("button", name="图标: edit 编辑").click()
        page.wait_for_selector(".ant-modal", timeout=5000)

        # 勾选"采购订单"
        page.get_by_role("checkbox", name="采购订单").check()

        # 取消"销售订单"（如果已勾选）
        sales_order_check = page.get_by_role("checkbox", name="销售订单")
        if sales_order_check.is_checked():
            sales_order_check.uncheck()

        # 点击"确定"保存
        page.get_by_role("button", name="确 定").click()
        page.wait_for_selector(".ant-message-success", timeout=5000)
        page.wait_for_selector(".ant-modal", state="hidden", timeout=3000)

        # 再次打开编辑页，验证权限勾选状态与保存一致
        row.get_by_role("button", name="图标: edit 编辑").click()
        page.wait_for_selector(".ant-modal", timeout=5000)

        # 断言：采购订单已勾选
        expect(page.get_by_role("checkbox", name="采购订单")).to_be_checked()
        # 断言：销售订单未勾选
        expect(page.get_by_role("checkbox", name="销售订单")).not_to_be_checked()

        # 关闭弹窗
        page.get_by_role("button", name="Close").click()
        page.wait_for_selector(".ant-modal", state="hidden", timeout=3000)

        # 清理：删除测试角色
        row.get_by_role("button", name="图标: delete 删除").click()
        page.get_by_role("button", name="确 定").click()
        page.wait_for_selector(".ant-message-success", timeout=5000)
        expect(page.locator("tr:has-text('测试角色')")).to_have_count(0)

    # ==================== 辅助方法 ====================
    def create_role_and_account(self, page, role_name, permissions):
        # 创建角色和账号
        # - role_name: 角色名称（如"采购管理员"）
        # - permissions: 权限列表，如["采购管理", "采购订单", "采购退货", "采购报表"]

        self.logout_and_login_as(page, "管理员")

        # ---------- 进入角色管理 ----------
        page.locator("div").filter(has_text=re.compile(r"^系统管理$")).click()
        page.get_by_role("menuitem", name="角色管理").click()
        page.wait_for_load_state("networkidle")

        # ---------- 新增角色 ----------
        page.get_by_role("button", name="图标: plus 新增角色").click()
        page.wait_for_selector(".ant-modal", timeout=5000)

        # 填写角色名称
        page.get_by_role("textbox").nth(1).fill(role_name)

        # 勾选权限
        for perm in permissions:
            checkbox = page.get_by_role("checkbox", name=perm)
            if checkbox.is_visible():
                checkbox.check()

        # 保存角色
        page.get_by_role("button", name="确 定").click()
        page.wait_for_selector(".ant-message-success", timeout=5000)
        page.wait_for_selector(".ant-modal", state="hidden", timeout=3000)

        # ---------- 创建员工账号 ----------
        page.get_by_role("menuitem", name="员工账号").click()
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="图标: plus 新增账号").click()
        page.wait_for_selector(".ant-modal", timeout=5000)

        # 填写用户名（第1个textbox）
        page.get_by_role("textbox").nth(1).fill(role_name)

        # 填写姓名（第2个textbox）
        page.get_by_role("textbox").nth(2).fill("员工" + role_name[:2])

        # 选择性别（男）
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="男").click()

        # 选择状态（启用）
        page.locator("div:nth-child(6) > .ant-col.ant-col-16 > .ant-form-item-control > .ant-form-item-children > .ant-select > .ant-select-selection > .ant-select-selection__rendered").click()
        page.get_by_role("option", name="启用").click()

        # 绑定角色（选择刚创建的角色）
        page.locator(".ant-select-selection.ant-select-selection--multiple > .ant-select-selection__rendered").click()
        page.get_by_role("option", name=role_name).click()

        # 保存账号
        page.get_by_role("button", name="确 定").click()
        page.wait_for_selector(".ant-message-success", timeout=5000)
        page.wait_for_selector(".ant-modal", state="hidden", timeout=3000)

    def logout_and_login_as(self, page, username):
        # 退出当前登录，用指定用户名登录
        # 直接跳转到登录页
        page.goto("http://8.156.85.50:8080/#/user/login")
        page.wait_for_load_state("networkidle")

        # 输入用户名密码
        page.locator("input[type='text']").fill(username)
        page.locator("input[type='password']").fill("123456")
        page.get_by_role("button", name="登 录").click()
        page.wait_for_selector("text=客户管理", timeout=30000)
        page.wait_for_load_state("networkidle")

    def delete_role_and_account(self, page, role_name, username):
        # 删除账号和角色（先删账号，再删角色）
        # - role_name: 角色名称
        # - username: 账号用户名（通常与角色名相同）

        print(f"🔍 开始清理角色: {role_name}, 账号: {username}")

        # 先切回管理员
        self.logout_and_login_as(page, "管理员")

        # ---------- 删除员工账号 ----------
        # 进入员工账号页面（直接点击菜单）
        page.locator("div").filter(has_text=re.compile(r"^系统管理$")).click()
        page.wait_for_timeout(300)
        page.get_by_role("menuitem", name="员工账号").click()
        page.wait_for_load_state("networkidle")

        # 尝试搜索账号（如果有搜索框）
        # 如果表格没有搜索框，直接查找行
        row = page.locator(f"tr:has-text('{username}')")
        if row.count() == 0:
            # 尝试滚动或等待
            page.wait_for_timeout(1000)
            row = page.locator(f"tr:has-text('{username}')")

        if row.count() > 0:
            row.get_by_role("button", name="图标: delete 删除").click()
            page.get_by_role("button", name="确 定").click()
            page.wait_for_selector(".ant-message-success", timeout=5000)
            page.wait_for_selector(".ant-message-success", state="hidden", timeout=5000)
            # 验证删除成功
            expect(page.locator(f"tr:has-text('{username}')")).to_have_count(0)
            print(f"✅ 账号 {username} 已删除")
        else:
            print(f"⚠️ 未找到账号 {username}，可能已被删除")

        # ---------- 删除角色 ----------
        page.get_by_role("menuitem", name="角色管理").click()
        page.wait_for_load_state("networkidle")

        row = page.locator(f"tr:has-text('{role_name}')")
        if row.count() == 0:
            page.wait_for_timeout(1000)
            row = page.locator(f"tr:has-text('{role_name}')")

        if row.count() > 0:
            row.get_by_role("button", name="图标: delete 删除").click()
            page.get_by_role("button", name="确 定").click()
            page.wait_for_selector(".ant-message-success", timeout=5000)
            page.wait_for_selector(".ant-message-success", state="hidden", timeout=5000)
            expect(page.locator(f"tr:has-text('{role_name}')")).to_have_count(0)
            print(f"✅ 角色 {role_name} 已删除")
        else:
            print(f"⚠️ 未找到角色 {role_name}，可能已被删除")


    def click_submenu(self, page, parent_menu, submenu_text):
        # 展开父菜单并点击子菜单
        parent = page.locator(f"text='{parent_menu}'").first
        parent.scroll_into_view_if_needed()
        parent.click()
        page.wait_for_timeout(500)

        # 尝试通过 role 定位子菜单
        try:
            submenu = page.get_by_role("menuitem", name=submenu_text)
            submenu.wait_for(state="visible", timeout=3000)
            submenu.scroll_into_view_if_needed()
            submenu.click()
        except:
            # 若超时，可能菜单未展开，再次点击父菜单
            parent.click()
            page.wait_for_timeout(300)
            submenu = page.get_by_role("menuitem", name=submenu_text)
            submenu.wait_for(state="visible", timeout=5000)
            submenu.scroll_into_view_if_needed()
            submenu.click()
        page.wait_for_load_state("networkidle")

    def verify_permission_denied(self, page):
        # 验证出现"未添加操作权限"提示
        expect(page.get_by_text("未添加操作权限").first).to_be_visible()
        # 等待提示消失，避免影响后续操作
        page.wait_for_selector("text=未添加操作权限", state="hidden", timeout=5000)

    def verify_purchase_order_page_fields(self, page):
        # 验证采购开单页面字段渲染
        expect(page.locator(".ant-select-selection__rendered").first).to_be_visible()
        expect(page.locator(".ant-select-selection__rendered").nth(1)).to_be_visible()
        expect(page.locator(".ant-select-selection__rendered").nth(2)).to_be_visible()
        expect(page.get_by_placeholder("请选择日期")).to_be_visible()
        expect(page.get_by_role("button", name="添加产品")).to_be_visible()
        expect(page.get_by_role("button", name="保 存")).to_be_visible()

    def verify_sales_order_page_fields(self, page):
        # 验证销售开单页面字段渲染
        expect(page.locator(".ant-select-selection__rendered").first).to_be_visible()
        expect(page.locator(".ant-select-selection__rendered").nth(1)).to_be_visible()
        expect(page.locator(".ant-select-selection__rendered").nth(2)).to_be_visible()
        expect(page.get_by_placeholder("请选择日期")).to_be_visible()
        expect(page.get_by_role("button", name="添加产品")).to_be_visible()
        expect(page.get_by_role("button", name="保 存")).to_be_visible()

    # ==================== TC-UI-052+053 采购管理员权限验证 ====================
    def test_purchase_admin_permission_validation(self, logged_page):
        page = logged_page
        role_name = "采购管理员"

        # 创建角色和账号
        self.create_role_and_account(page, role_name, ["采购管理", "采购订单", "采购退货", "采购报表"])

        # 登录采购管理员
        self.logout_and_login_as(page, role_name)

        # 验证采购开单（有权限）页面字段渲染
        self.click_submenu(page, "采购管理", "采购开单")
        self.verify_purchase_order_page_fields(page)
        page.goto("http://8.156.85.50:8080/#/home")


        # 点击销售开单 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "销售管理", "销售开单")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")


        # 点击销售退货 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "销售管理", "销售退货")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")

        # 清理
        self.delete_role_and_account(page, role_name, role_name)

    # ==================== TC-UI-056+057 销售管理员权限验证 ====================
    def test_sales_admin_permission_validation(self, logged_page):
        page = logged_page
        role_name = "销售管理员"

        # 创建角色和账号
        self.create_role_and_account(page, role_name, ["销售管理", "销售订单", "销售退货", "销售报表"])

        # 登录销售管理员
        self.logout_and_login_as(page, role_name)

        # 验证销售开单（有权限）页面字段渲染
        self.click_submenu(page, "销售管理", "销售开单")
        self.verify_sales_order_page_fields(page)
        page.goto("http://8.156.85.50:8080/#/home")

        # 点击采购开单 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "采购管理", "采购开单")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")

        # 点击采购退货 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "采购管理", "采购退货")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")

        # 清理
        self.delete_role_and_account(page, role_name, role_name)

    # ==================== TC-UI-060 仓管员-菜单可见性验证 ====================
    def test_warehouse_admin_permission_validation(self, logged_page):
        page = logged_page
        role_name = "仓管员"

        self.create_role_and_account(page, role_name, ["库存管理", "入库业务", "出库业务", "盘点业务", "调拨业务", "库存结存"])

        self.logout_and_login_as(page, role_name)

        # 验证入库任务（有权限）页面加载
        self.click_submenu(page, "库存管理", "入库任务")
        expect(page.locator("table")).to_be_visible()
        page.goto("http://8.156.85.50:8080/#/home")

        # 点击采购开单 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "采购管理", "采购开单")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")
        

        self.delete_role_and_account(page, role_name, role_name)

    # ==================== TC-UI-066 财务角色-菜单可见性验证 ====================
    def test_finance_admin_permission_validation(self, logged_page):
        page = logged_page
        role_name = "财务角色"

        self.create_role_and_account(page, role_name, ["往来管理", "应付账款", "付款业务", "应收账款", "收款业务", "资金流水"])

        self.logout_and_login_as(page, role_name)

        # 验证付款业务（有权限）页面加载
        self.click_submenu(page, "财务管理", "付款")
        expect(page.get_by_role("button", name="图标: plus 新增付款单")).to_be_visible()
        page.goto("http://8.156.85.50:8080/#/home")

        # 点击采购开单 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "采购管理", "采购开单")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")

        # 点击销售开单 -> 弹出"未添加操作权限"（无权限）
        self.click_submenu(page, "销售管理", "销售开单")
        self.verify_permission_denied(page)
        page.goto("http://8.156.85.50:8080/#/home")

        self.delete_role_and_account(page, role_name, role_name)

    # ==================== TC-UI-071 仅看板角色验证 ====================
    def test_dashboard_only_role(self, logged_page):
        page = logged_page
        role_name = "仅看板角色"

        self.create_role_and_account(page, role_name, ["数据看板", "销售走势", "销售前十产品", "订单收款明细"])

        self.logout_and_login_as(page, role_name)

        # 验证销售走势（有权限）页面加载
        page.locator("text='数据看板'").click()
        page.wait_for_timeout(500)
        # 使用更通用的定位方式
        page.locator("text=销售走势").first.click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("canvas").first).to_be_visible()
        page.goto("http://8.156.85.50:8080/#/home")


        # 点击报表统计 -> 弹出"未添加操作权限"（无权限）
        if page.locator("text='报表统计'").count() > 0:
            page.locator("text='报表统计'").click()
            page.wait_for_timeout(300)
            page.get_by_role("menuitem", name="销售报表").click()
            page.wait_for_load_state("networkidle")
            self.verify_permission_denied(page)
            page.goto("http://8.156.85.50:8080/#/home")

        self.delete_role_and_account(page, role_name, role_name)

    # ==================== TC-UI-072 仅报表角色验证 ====================
    def test_report_only_role(self, logged_page):
        page = logged_page
        role_name = "仅报表角色"

        self.create_role_and_account(page, role_name, ["报表统计", "销售报表", "采购报表", "库存报表", "收支统计"])

        self.logout_and_login_as(page, role_name)

        # 验证销售报表（有权限）页面加载
        page.locator("text='报表统计'").click()
        page.wait_for_timeout(500)
        page.get_by_role("menuitem", name="销售报表").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("table").first).to_be_visible()
        page.goto("http://8.156.85.50:8080/#/home")

        # 点击采购开单 -> 弹出"未添加操作权限"（无权限）
        if page.locator("text='采购管理'").count() > 0:
            page.locator("text='采购管理'").click()
            page.wait_for_timeout(300)
            page.get_by_role("menuitem", name="采购开单").click()
            page.wait_for_load_state("networkidle")
            self.verify_permission_denied(page)
            page.goto("http://8.156.85.50:8080/#/home")

        self.delete_role_and_account(page, role_name, role_name)