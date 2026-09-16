import pytest
from django.utils import timezone
from datetime import timedelta

# 共享 fixtures 从 conftest 自动获取
from apps.purchase.models import PurchaseOrder, PurchaseGoods
from apps.purchase.models import PurchaseReturnOrder, PurchaseReturnGoods
from apps.stock_out.models import StockOutOrder, StockOutGoods, StockOutRecord
from apps.flow.models import InventoryFlow
from apps.goods.models import Inventory


@pytest.fixture
def purchase_order_completed(db, admin_user, product_a, supplier_active, warehouse_active):
    # 创建一个已完成的采购单（模拟 TC-001 执行后的状态：库存=60）
    # 1. 确保库存记录存在并设为 60
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

    # 2. 创建采购单（仅作为关联数据，不参与库存变动）
    purchase_order = PurchaseOrder.objects.create(
        number='CG202608130001',
        warehouse=warehouse_active,
        supplier=supplier_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        enable_auto_stock_in=False,
        total_quantity=50.0,
        total_amount=5000.0,
        arrears_amount=5000.0,
        creator=admin_user,
        team=admin_user.team,
    )

    # 3. 创建采购明细
    PurchaseGoods.objects.create(
        purchase_order=purchase_order,
        goods=product_a,
        purchase_quantity=50.0,
        purchase_price=100.0,
        total_amount=5000.0,
        team=admin_user.team,
    )

    # 4. 创建已完成的入库单（可选，但退货视图可能关联）
    from apps.stock_in.models import StockInOrder, StockInGoods
    stock_in_order = StockInOrder.objects.create(
        number='RK202608130001',
        warehouse=warehouse_active,
        type=StockInOrder.Type.PURCHASE,
        purchase_order=purchase_order,
        total_quantity=50.0,
        remain_quantity=0.0,
        is_completed=True,
        creator=admin_user,
        team=admin_user.team,
    )
    StockInGoods.objects.create(
        stock_in_order=stock_in_order,
        goods=product_a,
        stock_in_quantity=50.0,
        remain_quantity=0.0,
        is_completed=True,
        team=admin_user.team,
    )

    return purchase_order


@pytest.mark.django_db
class TestPurchaseReturnFlow:
    # 采购退货反向流程测试（TC-CHAIN-003）

    def test_purchase_return_positive_flow(
        self,
        api_client,
        admin_user,
        product_a,
        supplier_active,
        warehouse_active,
        purchase_order_completed,
    ):
        # ========== 步骤1：发起采购退货 ==========
        return_data = {
            'number': 'CGTH202608130001',
            'purchase_order': purchase_order_completed.id,
            'warehouse': warehouse_active.id,
            'supplier': supplier_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_out': False,   # 手动出库
            'purchase_return_goods_items': [  # 序列化器字段名
                {
                    'purchase_goods': purchase_order_completed.purchase_goods_set.first().id,
                    'goods': product_a.id,
                    'return_quantity': 10.0,
                    'return_price': 100.0,
                }
            ]
        }

        url = '/api/purchase_return_orders/'
        response = api_client.post(url, return_data, format='json')
        assert response.status_code == 201, f"发起采购退货失败: {response.content}"

        return_order_id = response.data['id']
        return_order = PurchaseReturnOrder.objects.get(id=return_order_id)

        # 验证退货单总金额（10 * 100 = 1000）
        assert return_order.total_amount == 1000.0, f"退货总金额应为1000，实际{return_order.total_amount}"

        # ========== 步骤2：系统自动生成出库通知单 ==========
        # enable_auto_stock_out=False 时，系统会创建 StockOutOrder（类型为 PURCHASE）
        stock_out_order = StockOutOrder.objects.get(purchase_return_order=return_order)
        assert stock_out_order.is_completed is False, "出库通知单不应已完成"
        assert stock_out_order.total_quantity == 10.0

        # ========== 步骤3：执行退货出库（创建出库记录） ==========
        stock_out_goods = StockOutGoods.objects.get(
            stock_out_order=stock_out_order,
            goods=product_a,
        )

        stock_out_record_data = {
            'stock_out_order': stock_out_order.id,
            'warehouse': warehouse_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [  # 与 TC-002 相同
                {
                    'stock_out_goods': stock_out_goods.id,
                    'stock_out_quantity': 10.0,
                }
            ]
        }

        record_url = '/api/stock_out_records/'
        response = api_client.post(record_url, stock_out_record_data, format='json')
        assert response.status_code == 201, f"执行退货出库失败: {response.content}"

        # ========== 验证结果 ==========
        # 1. 产品库存变为 50（原60 - 10）
        inventory = Inventory.objects.get(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
        )
        assert inventory.total_quantity == 50.0, f"库存不符，实际为 {inventory.total_quantity}"

        # 2. 生成库存流水（STOCK_OUT 类型）
        flows = InventoryFlow.objects.filter(
            goods=product_a,
            quantity_change=10.0,   # 存储变动的绝对值
            type=InventoryFlow.Type.STOCK_OUT,
        )
        assert flows.exists(), "未产生库存流水记录"
        flow = flows.first()
        assert flow.quantity_before == 60.0, f"变化前库存应为60，实际{flow.quantity_before}"
        assert flow.quantity_after == 50.0, f"变化后库存应为50，实际{flow.quantity_after}"

        # 3. 财务应付减少1000元（PurchaseReturnOrder.arrears_amount）
        return_order.refresh_from_db()
        assert return_order.arrears_amount == 1000.0, f"应付金额应为1000，实际{return_order.arrears_amount}"

        # 额外验证：出库通知单已完成
        stock_out_order.refresh_from_db()
        assert stock_out_order.is_completed is True, "出库通知单未标记完成"