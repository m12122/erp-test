import re
import pytest
from playwright.sync_api import expect

BASE_URL = "http://8.156.85.50:8080"

# 全局变量用于传递单号
purchase_order_no = None
sales_order_no = None

from datetime import datetime
today_day = datetime.now().day


@pytest.mark.usefixtures("logged_page")
class TestERPE2E:
    
    # ========== TC-E2E-001 采购入库完整流程 ==========
    def test_purchase_inbound_flow(self, logged_page):
        global purchase_order_no
        page = logged_page

        # 采购开单
        page.locator(".ant-menu-submenu-title:has-text('采购管理')").click()
        page.locator(".ant-menu-item:has-text('采购开单')").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # 选择供应商、仓库、经手人
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认供应商").click()
        page.locator(".ant-select-selection__rendered").nth(1).click()
        page.get_by_role("option", name="默认仓库").click()
        page.locator(".ant-select-selection__rendered").nth(2).click()
        page.get_by_role("option", name="管理员").click()

        # 日期
        page.get_by_placeholder("请选择日期").click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()

        # 添加产品
        page.get_by_role("button", name="添加产品").click()
        page.get_by_role("button", name="选 择").click()

        # 等待包含 spinbutton 的单元格出现
        page.wait_for_selector("[role='spinbutton']", timeout=10000)

        # 使用录制中的选择器填写数量 50、单价 100、税率 0
        page.get_by_role("cell", name="Increase Value Decrease Value 1", exact=True).get_by_role("spinbutton").fill("50")
        page.get_by_role("cell", name="Increase Value Decrease Value 10").get_by_role("spinbutton").fill("100")
        page.get_by_role("cell", name="Increase Value Decrease Value %").get_by_role("spinbutton").fill("0")

        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        #---------- 断言1: 页面跳转至采购记录 ----------
        page.wait_for_url("**/#/purchasing/purchase_record", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        
        #---------- 断言2: 成功提示 ----------
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "保存采购单后未出现成功提示"

        #---------- 断言3: 获取采购单号 ----------
        headers = page.locator("table thead th").all_text_contents()
        col_idx = None
        for i, header in enumerate(headers, start=1):
            if "采购编号" in header:
                col_idx = i
                break
        assert col_idx is not None
        purchase_no = page.locator(f"table tbody tr:first-child td:nth-child({col_idx})").first.text_content().strip()
        assert purchase_no.startswith("CG")
        purchase_order_no = purchase_no
        print(f"采购单号: {purchase_order_no}")

        # 执行入库
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="入库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # 获取第一行“单号”列的文本
        page.wait_for_selector("table thead th", timeout=10000)
        headers = page.locator("table thead th").all_text_contents()
        order_no_col = None
        for i, h in enumerate(headers, start=1):
            if "单号" in h:
                order_no_col = i
                break
        assert order_no_col is not None, "未找到单号列"
        task_no = page.locator(f"table tbody tr:first-child td:nth-child({order_no_col})").text_content().strip()
        print(f"入库任务单号: {task_no}")

        page.locator("table tbody tr:first-child button:has-text('入 库')").first.click()
        page.wait_for_url("**/#/warehouse/inStock_create*", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=10000)

        # 经手人
        page.locator(".ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 执行日期
        date_input = page.locator("input[placeholder='请选择日期']").first
        date_input.click()
        page.wait_for_timeout(300)
        today_cell = page.locator(".ant-calendar-today")
        if today_cell.count() > 0:
            today_cell.click()
        else:
            page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        actual_date = date_input.input_value()
        assert actual_date, "日期未成功选择"
        print(f"已选日期: {actual_date}")

        # 保存入库
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click(timeout=10000)

        #---------- 断言4: 入库成功后页面跳转至任务列表 ----------
        page.wait_for_url("**/#/warehouse/*", timeout=15000)
        #---------- 断言5: 成功提示出现 ----------
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "入库保存后未出现成功提示"
        # ---------- 断言6: 入库任务消失 ----------
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="入库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)
        # 查找该单号所在行
        row = page.locator(f"table tbody tr:has-text('{task_no}')")
        assert row.count() == 0, f"任务单号 {task_no} 仍存在，入库任务未消失"
        print(f"入库任务 {task_no} 已消失，验证通过")

        print("✅ TC-E2E-001 采购入库E2E验证通过")



    # ========== TC-E2E-002 销售出库完整流程 ==========
    def test_sales_outbound_flow(self, logged_page):
        global sales_order_no
        page = logged_page
        
        # 销售开单
        page.locator("div").filter(has_text=re.compile(r"^销售管理$")).click()
        page.get_by_role("menuitem", name="销售开单").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # 选择仓库、客户、经手人
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="默认仓库").click()
        page.locator(".ant-select-selection__rendered").nth(1).click()
        page.get_by_role("option", name="默认客户").click()
        page.locator(".ant-select-selection__rendered").nth(2).click()
        page.get_by_role("option", name="管理员").click()

        # 日期
        page.get_by_placeholder("请选择日期").click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()
        

        # 等待包含 spinbutton 的单元格出现
        page.wait_for_selector("[role='spinbutton']", timeout=10000)

        # 添加产品
        page.get_by_role("button", name="添加产品").click()
        page.get_by_role("button", name="选 择").click()
        page.wait_for_selector("[role='spinbutton']", timeout=10000)
        # 填写数量 20、单价 150、税率 0
        page.get_by_role("spinbutton").nth(0).fill("20")
        page.get_by_role("spinbutton").nth(1).fill("150")
        page.get_by_role("spinbutton").nth(2).fill("0")


        # 保存
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()

        # 获取销售单号
        page.wait_for_url("**/#/sale/sale_record", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "保存销售单后未出现成功提示"

        headers = page.locator("table thead th").all_text_contents()
        col_idx = None
        for i, header in enumerate(headers, start=1):
            if "销售编号" in header:
                col_idx = i
                break
        assert col_idx is not None
        sales_no = page.locator(f"table tbody tr:first-child td:nth-child({col_idx})").first.text_content().strip()
        assert sales_no.startswith("XS")
        sales_order_no = sales_no
        print(f"销售单号: {sales_order_no}")

        # 执行出库
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="出库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        page.wait_for_selector("table thead th", timeout=10000)
        headers = page.locator("table thead th").all_text_contents()
        order_no_col = None
        for i, h in enumerate(headers, start=1):
            if "单号" in h:
                order_no_col = i
                break
        assert order_no_col is not None, "未找到单号列"
        task_no = page.locator(f"table tbody tr:first-child td:nth-child({order_no_col})").text_content().strip()
        print(f"出库任务单号: {task_no}")

        page.locator("table tbody tr:first-child button:has-text('出 库')").first.click()
        page.wait_for_url("**/#/warehouse/outStock_create*", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=10000)

        # 经手人
        page.locator(".ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()

        # 日期
        date_input = page.locator("input[placeholder='请选择日期']").first
        date_input.click()
        page.wait_for_timeout(300)
        today_cell = page.locator(".ant-calendar-today")
        if today_cell.count() > 0:
            today_cell.click()
        else:
            page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # 保存出库
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click(timeout=10000)

        page.wait_for_url("**/#/warehouse/*", timeout=15000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "出库保存后未出现成功提示"
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="出库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)
        row = page.locator(f"table tbody tr:has-text('{task_no}')")
        assert row.count() == 0, f"任务单号 {task_no} 仍存在，出库任务未消失"
        print(f"出库任务 {task_no} 已消失，验证通过")

        print("✅ TC-E2E-002 销售出库E2E验证通过")


    # ========== TC-E2E-003 采购退货完整流程 ==========
    def test_purchase_return_flow(self, logged_page):
        global purchase_order_no
        page = logged_page
        
        # 发起采购退货
        page.locator("div").filter(has_text=re.compile(r"^采购管理$")).click()
        page.get_by_role("menuitem", name="采购退货").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # 选择采购单
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name=purchase_order_no).click()
        page.get_by_placeholder("请选择日期").click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()

        # 填写退货数量 10
        page.get_by_role("cell", name=f"Increase Value Decrease Value 50").get_by_role("spinbutton").fill("10")
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()
        page.wait_for_url("**/#/purchasing/return_record", timeout=30000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "采购退货保存后未出现成功提示"

        # 执行退货出库
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="出库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        page.wait_for_selector("table thead th", timeout=10000)
        headers = page.locator("table thead th").all_text_contents()
        order_no_col = None
        for i, h in enumerate(headers, start=1):
            if "单号" in h:
                order_no_col = i
                break
        assert order_no_col is not None, "未找到单号列"
        task_no = page.locator(f"table tbody tr:first-child td:nth-child({order_no_col})").text_content().strip()
        print(f"退货出库任务单号: {task_no}")


        page.locator("table tbody tr:first-child button:has-text('出 库')").first.click()
        page.wait_for_url("**/#/warehouse/outStock_create*", timeout=30000)
        page.locator(".ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()
        date_input = page.locator("input[placeholder='请选择日期']").first
        date_input.click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()
        page.keyboard.press("Escape")
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click(timeout=10000)

        page.wait_for_url("**/#/warehouse/outStock*", timeout=15000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "退货出库保存后未出现成功提示"

        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="出库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)
        row = page.locator(f"table tbody tr:has-text('{task_no}')")
        assert row.count() == 0, f"退货出库任务单号 {task_no} 仍存在，任务未消失"
        print(f"退货出库任务 {task_no} 已消失，验证通过")

        print("✅ TC-E2E-003 采购退货E2E验证通过")
        

    # ========== TC-E2E-004 销售退货完整流程 ==========
    def test_sales_return_flow(self, logged_page):
        global sales_order_no
        page = logged_page

        # 发起销售退货
        page.locator("div").filter(has_text=re.compile(r"^销售管理$")).click()
        page.get_by_role("menuitem", name="销售退货").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # 选择销售单
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name=sales_order_no).click()
        page.get_by_placeholder("请选择日期").click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()

        # 填写退货数量 5
        page.get_by_role("cell", name=f"Increase Value Decrease Value 20").get_by_role("spinbutton").fill("5")
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click()
        page.wait_for_url("**/#/sale/sale_return_record", timeout=30000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "销售退货保存后未出现成功提示"

        # 执行退货入库
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="入库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        page.wait_for_selector("table thead th", timeout=10000)
        headers = page.locator("table thead th").all_text_contents()
        order_no_col = None
        for i, h in enumerate(headers, start=1):
            if "单号" in h:
                order_no_col = i
                break
        assert order_no_col is not None, "未找到单号列"
        task_no = page.locator(f"table tbody tr:first-child td:nth-child({order_no_col})").text_content().strip()
        print(f"退货入库任务单号: {task_no}")


        page.locator("table tbody tr:first-child button:has-text('入 库')").first.click()
        page.wait_for_url("**/#/warehouse/inStock_create*", timeout=30000)
        page.locator(".ant-select-selection__rendered").click()
        page.get_by_role("option", name="管理员").click()
        date_input = page.locator("input[placeholder='请选择日期']").first
        date_input.click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()
        page.keyboard.press("Escape")
        page.get_by_role("button", name="保 存").click()
        page.get_by_role("button", name="确 定").click(timeout=10000)

        page.wait_for_url("**/#/warehouse/inStock*", timeout=15000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "退货入库保存后未出现成功提示"
        page.locator("div").filter(has_text=re.compile(r"^库存管理$")).click()
        page.get_by_role("menuitem", name="入库任务").click()
        page.wait_for_load_state("networkidle", timeout=30000)
        row = page.locator(f"table tbody tr:has-text('{task_no}')")
        assert row.count() == 0, f"退货入库任务单号 {task_no} 仍存在，任务未消失"
        print(f"退货入库任务 {task_no} 已消失，验证通过")

        print("✅ TC-E2E-004 销售退货E2E验证通过")

     
    # ========== TC-E2E-005 账户转账完整流程 ==========
    def test_account_transfer_flow(self, logged_page):
        page = logged_page

        # 进入账户转账
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="账户转账").click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # 点击新增账户转账
        page.get_by_role("button", name="图标: plus 新增账户转账").click()
        page.wait_for_load_state("networkidle", timeout=10000)

        # 选择转出账户（微信账户）
        page.locator(".ant-select-selection__rendered").first.click()
        page.get_by_role("option", name="微信账户").click()
        # 选择转出时间
        from datetime import datetime
        today_day = datetime.now().day
        page.get_by_role("textbox", name="请选择日期").first.click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()

        # 选择转入账户（银行账户）
        page.locator(".ant-select-selection__rendered").nth(1).click()
        page.get_by_role("option", name="银行账户").click()
        # 转入时间
        page.get_by_role("textbox", name="请选择日期").nth(1).click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()

        # 输入金额 2000
        page.get_by_role("spinbutton").first.fill("2000")

        # 经手人
        page.locator(".ant-select-selection__rendered").nth(3).click()
        page.get_by_role("option", name="管理员").click()
        # 处理时间
        page.get_by_role("textbox", name="请选择日期").nth(2).click()
        page.locator(f".ant-calendar-date:not(.ant-calendar-other-month):has-text('{today_day}')").first.click()

        # 点击确定
        page.get_by_role("button", name="确 定").click()

        # 断言1: 转账成功提示
        page.wait_for_selector(".ant-message-success", timeout=10000)
        success_msg = page.locator(".ant-message-success")
        assert success_msg.count() > 0, "转账成功后未出现成功提示"
        print(f"转账成功: {success_msg.text_content()}")


        # 断言2: 转账记录新增（验证最新记录金额为2000）
        # 重新进入转账记录列表
        page.locator("div").filter(has_text=re.compile(r"^财务管理$")).click()
        page.get_by_role("menuitem", name="账户转账").click()
        page.wait_for_load_state("networkidle", timeout=30000)
        headers = page.locator("table thead th").all_text_contents()
        amount_col = None
        for i, h in enumerate(headers, start=1):
            if "金额" in h:
                amount_col = i
                break
        assert amount_col is not None, "未找到金额列"
        latest_amount_text = page.locator(f"table tbody tr:first-child td:nth-child({amount_col})").text_content().strip()

        amount_match = re.search(r"[\d,]+\.?\d*", latest_amount_text)
        assert amount_match, "金额列无有效数字"
        latest_amount = float(amount_match.group().replace(',', ''))
        assert latest_amount == 2000.0, f"转账记录金额应为2000，实际: {latest_amount}"
        print(f"最新转账记录金额: {latest_amount}")

        # 断言3: 余额界面回显正常（不验证具体数值）
        page.locator("div").filter(has_text=re.compile(r"^基础数据$")).click()
        page.get_by_role("menuitem", name="结算账户").click()
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_selector("table", timeout=10000)

        headers = page.locator("table thead th").all_text_contents()
        balance_col_index = None
        for i, header in enumerate(headers, start=1):
            if "账户余额" in header:
                balance_col_index = i
                break
        assert balance_col_index is not None, "未找到‘账户余额’列"

        wechat_row = page.locator("tr:has-text('微信账户')")
        wechat_balance_text = wechat_row.locator(f"td:nth-child({balance_col_index})").text_content().strip()
        assert wechat_balance_text, "微信账户余额显示为空"

        bank_row = page.locator("tr:has-text('银行账户')")
        bank_balance_text = bank_row.locator(f"td:nth-child({balance_col_index})").text_content().strip()
        assert bank_balance_text, "银行账户余额显示为空"

        print("✅ TC-E2E-005 账户转账E2E验证通过")