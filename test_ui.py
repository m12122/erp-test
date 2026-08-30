import re
import pytest
from playwright.sync_api import expect, sync_playwright
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