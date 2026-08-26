import pytest
from django.utils import timezone
from datetime import timedelta

# 共享 fixtures 从 conftest 自动获取
from apps.sales.models import SalesOrder, SalesGoods
from apps.sales.models import SalesReturnOrder, SalesReturnGoods
from apps.stock_in.models import StockInOrder, StockInGoods, StockInRecord
from apps.flow.models import InventoryFlow
from apps.goods.models import Inventory
from apps.data.models import Client


@pytest.fixture
def client_active(db, admin_user):
    # 创建启用状态的客户
    return Client.objects.create(
        number='C001',
        name='测试客户',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def sales_order_completed(db, admin_user, product_a, client_active, warehouse_active):
    # 创建一个已完成的销售单（模拟 TC-002 执行后的状态：库存=40，已出库20个）
    # 1. 确保库存记录存在并设为 40
    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse_active,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 40.0, 'has_stock': True}
    )
    if not created:
        inventory.total_quantity = 40.0
        inventory.has_stock = True
        inventory.save()

    # 2. 创建销售单
    sales_order = SalesOrder.objects.create(
        number='XSD202608130001',
        warehouse=warehouse_active,
        client=client_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        enable_auto_stock_out=False,
        total_quantity=20.0,
        total_amount=3000.0,
        arrears_amount=3000.0,
        creator=admin_user,
        team=admin_user.team,
    )

    # 3. 创建销售明细
    SalesGoods.objects.create(
        sales_order=sales_order,
        goods=product_a,
        sales_quantity=20.0,
        sales_price=150.0,
        total_amount=3000.0,
        team=admin_user.team,
    )

    # 4. 创建已完成的出库单（StockOutOrder）
    from apps.stock_out.models import StockOutOrder, StockOutGoods
    stock_out_order = StockOutOrder.objects.create(
        number='CK202608130001',
        warehouse=warehouse_active,
        type=StockOutOrder.Type.SALES,
        sales_order=sales_order,
        total_quantity=20.0,
        remain_quantity=0.0,
        is_completed=True,
        creator=admin_user,
        team=admin_user.team,
    )
    StockOutGoods.objects.create(
        stock_out_order=stock_out_order,
        goods=product_a,
        stock_out_quantity=20.0,
        remain_quantity=0.0,
        is_completed=True,
        team=admin_user.team,
    )

    return sales_order


@pytest.mark.django_db
class TestSalesReturnFlow:
    # 销售退货反向流程测试（TC-CHAIN-004）

    def test_sales_return_positive_flow(
        self,
        api_client,
        admin_user,
        product_a,
        client_active,
        warehouse_active,
        sales_order_completed,
    ):
        # ========== 步骤1：发起销售退货 ==========
        return_data = {
            'number': 'XSTH202608130001',
            'sales_order': sales_order_completed.id,
            'warehouse': warehouse_active.id,
            'client': client_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_in': False,   # 手动入库
            'sales_return_goods_items': [    # 序列化器字段名
                {
                    'sales_goods': sales_order_completed.sales_goods_set.first().id,
                    'goods': product_a.id,
                    'return_quantity': 5.0,
                    'return_price': 150.0,
                }
            ]
        }

        url = '/api/sales_return_orders/'
        response = api_client.post(url, return_data, format='json')
        assert response.status_code == 201, f"发起销售退货失败: {response.content}"

        return_order_id = response.data['id']
        return_order = SalesReturnOrder.objects.get(id=return_order_id)

        # 验证退货单总金额（5 * 150 = 750）
        assert return_order.total_amount == 750.0, f"退货总金额应为750，实际{return_order.total_amount}"

        # ========== 步骤2：系统自动生成入库通知单 ==========
        # enable_auto_stock_in=False 时，系统会创建 StockInOrder（类型为 SALES_RETURN）
        stock_in_order = StockInOrder.objects.get(sales_return_order=return_order)
        assert stock_in_order.is_completed is False, "入库通知单不应已完成"
        assert stock_in_order.total_quantity == 5.0

        # ========== 步骤3：执行退货入库（创建入库记录） ==========
        stock_in_goods = StockInGoods.objects.get(
            stock_in_order=stock_in_order,
            goods=product_a,
        )

        stock_in_record_data = {
            'stock_in_order': stock_in_order.id,
            'warehouse': warehouse_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [  # 与 TC-001 相同
                {
                    'stock_in_goods': stock_in_goods.id,
                    'stock_in_quantity': 5.0,
                }
            ]
        }

        record_url = '/api/stock_in_records/'
        response = api_client.post(record_url, stock_in_record_data, format='json')
        assert response.status_code == 201, f"执行退货入库失败: {response.content}"

        # ========== 验证结果 ==========
        # 1. 产品库存变为 45（原40 + 5）
        inventory = Inventory.objects.get(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
        )
        assert inventory.total_quantity == 45.0, f"库存不符，实际为 {inventory.total_quantity}"

        # 2. 生成库存流水（SALES_RETURN 类型）
        flows = InventoryFlow.objects.filter(
            goods=product_a,
            quantity_change=5.0,   
            type=InventoryFlow.Type.STOCK_IN,
        )
        assert flows.exists(), "未产生库存流水记录"
        flow = flows.first()
        assert flow.quantity_before == 40.0, f"变化前库存应为40，实际{flow.quantity_before}"
        assert flow.quantity_after == 45.0, f"变化后库存应为45，实际{flow.quantity_after}"

        # 3. 财务应收减少750元（SalesReturnOrder.arrears_amount）
        return_order.refresh_from_db()
        assert return_order.arrears_amount == 750.0, f"退货单应收金额应为750，实际{return_order.arrears_amount}"

        # 额外验证：入库通知单已完成
        stock_in_order.refresh_from_db()
        assert stock_in_order.is_completed is True, "入库通知单未标记完成"