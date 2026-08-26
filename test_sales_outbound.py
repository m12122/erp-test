import pytest
from django.utils import timezone

# 共享 fixtures 从 conftest 自动获取
from apps.data.models import Client
from apps.sales.models import SalesOrder, SalesGoods
from apps.stock_out.models import StockOutOrder, StockOutGoods, StockOutRecord
from apps.flow.models import InventoryFlow


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
def inventory_a_stock_60(db, product_a, warehouse_active, admin_user):
    # 将产品A库存设置为60（模拟TC-001执行后的状态）
    from apps.goods.models import Inventory

    # 使用 get_or_create 确保记录存在
    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse_active,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 60.0, 'has_stock': True}
    )
    if not created:
        inventory.total_quantity = 60.0
        inventory.has_stock = True
        inventory.save()
    return inventory


@pytest.mark.django_db
class TestSalesOutboundFlow:
    # 销售出库正向流程测试（TC-CHAIN-002）

    def test_sales_outbound_positive_flow(
        self,
        api_client,
        admin_user,
        product_a,
        client_active,
        warehouse_active,
        inventory_a_stock_60,
    ):

        # ========== 步骤1：创建销售单 ==========
        sales_data = {
            'number': 'XSD202608130001',
            'warehouse': warehouse_active.id,
            'client': client_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_out': False,   # 手动出库
            'discount': 100,
            'sales_goods_items': [            # 与 SalesGoods 对应
                {
                    'goods': product_a.id,
                    'sales_quantity': 20.0,
                    'sales_price': 150.0,
                }
            ]
        }

        url = '/api/sales_orders/'            # apps/sales/urls.py
        response = api_client.post(url, sales_data, format='json')
        assert response.status_code == 201, f"创建销售单失败: {response.content}"
        sales_order_id = response.data['id']
        sales_order = SalesOrder.objects.get(id=sales_order_id)

        # 验证销售总金额
        assert sales_order.total_amount == 3000.0

        # ========== 步骤2：系统自动生成出库通知单 ==========
        stock_out_order = StockOutOrder.objects.get(sales_order=sales_order)
        assert stock_out_order.is_completed is False
        assert stock_out_order.total_quantity == 20.0

        # ========== 步骤3：执行出库（创建出库记录） ==========
        stock_out_goods = StockOutGoods.objects.get(
            stock_out_order=stock_out_order,
            goods=product_a,
        )

        stock_out_record_data = {
            'stock_out_order': stock_out_order.id,
            'warehouse': warehouse_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [
                {
                    'stock_out_goods': stock_out_goods.id,
                    'stock_out_quantity': 20.0,
                }
            ]
        }

        record_url = '/api/stock_out_records/'  # apps/stock_out/urls.py
        response = api_client.post(record_url, stock_out_record_data, format='json')
        assert response.status_code == 201, f"执行出库失败: {response.content}"

        # ========== 验证结果 ==========
        # 1. 库存变为 40
        inventory_a_stock_60.refresh_from_db()
        assert inventory_a_stock_60.total_quantity == 40.0

        # 2. 生成库存流水（STOCK_OUT 类型）
        flows = InventoryFlow.objects.filter(
            goods=product_a,
            quantity_change=20.0,
            type='stock_out',   # 出库类型
        )
        assert flows.exists()
        flow = flows.first()
        assert flow.quantity_before == 60.0
        assert flow.quantity_after == 40.0

        # 3. 财务应收（SalesOrder.arrears_amount 增加 3000）
        sales_order.refresh_from_db()
        assert sales_order.arrears_amount == 3000.0

        # 4. 出库通知单已完成
        stock_out_order.refresh_from_db()
        assert stock_out_order.is_completed is True