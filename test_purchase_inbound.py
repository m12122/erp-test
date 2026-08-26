import pytest
from django.utils import timezone

# 导入所需的模型
from apps.purchase.models import PurchaseOrder
from apps.stock_in.models import StockInOrder, StockInGoods
from apps.flow.models import InventoryFlow


@pytest.mark.django_db
class TestPurchaseInboundFlow:
    def test_purchase_inbound_positive_flow(
        self,
        api_client,
        admin_user,
        product_a,
        supplier_active,
        warehouse_active,
        inventory_a,
    ):
        # ========== 步骤1：创建采购单 ==========
        purchase_data = {
            'number': 'CG202608120001',
            'warehouse': warehouse_active.id,
            'supplier': supplier_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_in': False,
            'purchase_goods_items': [
                {
                    'goods': product_a.id,
                    'purchase_quantity': 50.0,
                    'purchase_price': 100.0,
                }
            ],
        }

        url = '/api/purchase_orders/'
        response = api_client.post(url, purchase_data, format='json')

        assert response.status_code == 201, f"创建采购单失败: {response.content}"
        purchase_order_id = response.data['id']
        purchase_order = PurchaseOrder.objects.get(id=purchase_order_id)

        # 验证采购单总金额
        assert purchase_order.total_amount == 5000.0

        # ========== 步骤2：系统自动生成入库通知单 ==========
        stock_in_order = StockInOrder.objects.get(purchase_order=purchase_order)
        assert stock_in_order.is_completed is False
        assert stock_in_order.total_quantity == 50.0

        # ========== 步骤3：执行入库 ==========
        stock_in_goods = StockInGoods.objects.get(
            stock_in_order=stock_in_order,
            goods=product_a,
        )

        stock_in_record_data = {
            'stock_in_order': stock_in_order.id,
            'warehouse': warehouse_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {
                    'stock_in_goods': stock_in_goods.id,
                    'stock_in_quantity': 50.0,
                }
            ],
        }

        record_url = '/api/stock_in_records/'
        response = api_client.post(record_url, stock_in_record_data, format='json')
        assert response.status_code == 201, f"执行入库失败: {response.content}"

        # ========== 验证结果 ==========
        # 1. 库存变为 60
        inventory_a.refresh_from_db()
        assert inventory_a.total_quantity == 60.0

        # 2. 生成库存流水记录
        flows = InventoryFlow.objects.filter(
            goods=product_a,
            quantity_change=50.0,
            type=InventoryFlow.Type.STOCK_IN,
        )
        assert flows.exists()
        flow = flows.first()
        assert flow.quantity_before == 10.0
        assert flow.quantity_after == 60.0

        # 3. 财务应付记录增加 5000 元
        purchase_order.refresh_from_db()
        assert purchase_order.arrears_amount == 5000.0

        # 4. 入库通知单已完成
        stock_in_order.refresh_from_db()
        assert stock_in_order.is_completed is True