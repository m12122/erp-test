import pytest
from django.utils import timezone
from rest_framework import status

from apps.stock_transfer.models import StockTransferOrder
from apps.stock_check.models import StockCheckOrder
from apps.stock_out.models import StockOutOrder, StockOutGoods, StockOutRecord
from apps.stock_in.models import StockInOrder, StockInGoods, StockInRecord
from apps.goods.models import Inventory
from apps.flow.models import InventoryFlow
from apps.data.models import Warehouse


# ==================== Fixtures ====================

@pytest.fixture
def warehouse_beijing(db, admin_user):
    # 北京仓库
    return Warehouse.objects.create(
        number='W001',
        name='北京仓',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def warehouse_shanghai(db, admin_user):
    # 上海仓库
    return Warehouse.objects.create(
        number='W002',
        name='上海仓',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def inventory_beijing_50(db, product_a, warehouse_beijing, admin_user):
    # 北京仓产品A库存50
    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse_beijing,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 50.0, 'has_stock': True}
    )
    if not created:
        inventory.total_quantity = 50.0
        inventory.has_stock = True
        inventory.save()
    return inventory


@pytest.fixture
def inventory_shanghai_0(db, product_a, warehouse_shanghai, admin_user):
    # 上海仓产品A库存0
    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse_shanghai,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 0.0, 'has_stock': False}
    )
    if not created:
        inventory.total_quantity = 0.0
        inventory.has_stock = False
        inventory.save()
    return inventory


# ==================== Test Class ====================

@pytest.mark.django_db
class TestStockTransferCheck:

    # ========== TC-API-035 库存调拨-正常创建与执行 ==========
    def test_stock_transfer_success(self, api_client, admin_user, product_a,
                                    warehouse_beijing, warehouse_shanghai,
                                    inventory_beijing_50, inventory_shanghai_0):
        # 正常调拨：北京仓50，调拨30至上海仓
        url = '/api/stock_transfer_orders/'
        data = {
            'number': 'DB202608170001',
            'out_warehouse': warehouse_beijing.id,
            'in_warehouse': warehouse_shanghai.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_transfer_goods_items': [
                {
                    'goods': product_a.id,
                    'stock_transfer_quantity': 30.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        transfer_order_id = response.data['id']
        transfer_order = StockTransferOrder.objects.get(id=transfer_order_id)
        assert transfer_order.total_quantity == 30.0

        # 出库：从北京仓出库30
        stock_out_order = StockOutOrder.objects.get(stock_transfer_order=transfer_order)
        stock_out_goods = stock_out_order.stock_out_goods_set.first()
        record_url = '/api/stock_out_records/'
        record_data = {
            'stock_out_order': stock_out_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [
                {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 30.0}
            ]
        }
        resp_out = api_client.post(record_url, record_data, format='json')
        assert resp_out.status_code == 201

        # 入库：上海仓入库30
        stock_in_order = StockInOrder.objects.get(stock_transfer_order=transfer_order)
        stock_in_goods = stock_in_order.stock_in_goods_set.first()
        record_in_url = '/api/stock_in_records/'
        record_in_data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': 30.0}
            ]
        }
        resp_in = api_client.post(record_in_url, record_in_data, format='json')
        assert resp_in.status_code == 201

        # 验证库存变化
        inventory_beijing_50.refresh_from_db()
        inventory_shanghai_0.refresh_from_db()
        assert inventory_beijing_50.total_quantity == 20.0
        assert inventory_shanghai_0.total_quantity == 30.0

        # 验证调拨记录生成
        assert StockTransferOrder.objects.filter(id=transfer_order_id).exists()
        assert transfer_order.is_void is False

    # ========== TC-API-036 调拨数量超出源仓库存校验 ==========
    def test_stock_transfer_exceeds_stock(self, api_client, admin_user, product_a,
                                          warehouse_beijing, warehouse_shanghai,
                                          inventory_beijing_50):
        # 调拨数量60，超出北京仓库存50，应报错
        url = '/api/stock_transfer_orders/'
        data = {
            'number': 'DB202608170002',
            'out_warehouse': warehouse_beijing.id,
            'in_warehouse': warehouse_shanghai.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_transfer_goods_items': [
                {
                    'goods': product_a.id,
                    'stock_transfer_quantity': 60.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')

        if response.status_code == status.HTTP_201_CREATED:
            transfer_order_id = response.data['id']
            stock_out_order = StockOutOrder.objects.get(stock_transfer_order_id=transfer_order_id)
            stock_out_goods = stock_out_order.stock_out_goods_set.first()
            record_url = '/api/stock_out_records/'
            record_data = {
                'stock_out_order': stock_out_order.id,
                'handler': admin_user.id,
                'handle_time': timezone.now().date(),
                'stock_out_record_goods_items': [
                    {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 60.0}
                ]
            }
            resp_out = api_client.post(record_url, record_data, format='json')
            assert resp_out.status_code == status.HTTP_400_BAD_REQUEST
            error_msg = str(resp_out.data).lower()
            assert '库存不足' in error_msg or 'insufficient' in error_msg
        else:
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            error_msg = str(response.data).lower()
            assert '库存不足' in error_msg or 'insufficient' in error_msg

    # ========== TC-API-037 库存盘点-盘亏验证 ==========
    def test_stock_check_loss(self, api_client, admin_user, product_a, warehouse_beijing):
        # 盘亏：账面40，实盘35，盘亏5
        # 确保库存记录存在并设为40
        inventory, created = Inventory.objects.get_or_create(
            warehouse=warehouse_beijing,
            goods=product_a,
            team=admin_user.team,
            defaults={'total_quantity': 40.0, 'has_stock': True}
        )
        if not created:
            inventory.total_quantity = 40.0
            inventory.has_stock = True
            inventory.save()

        url = '/api/stock_check_orders/'
        data = {
            'number': 'PD202608170001',
            'warehouse': warehouse_beijing.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_check_goods_Items': [
                {
                    'goods': product_a.id,
                    'actual_quantity': 35.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        check_order_id = response.data['id']
        check_order = StockCheckOrder.objects.get(id=check_order_id)

        assert check_order.status == StockCheckOrder.Status.LOSS
        stock_check_goods = check_order.stock_check_goods_set.first()
        assert stock_check_goods.book_quantity == 40.0
        assert stock_check_goods.actual_quantity == 35.0
        assert stock_check_goods.surplus_quantity == -5.0

        inventory.refresh_from_db()
        assert inventory.total_quantity == 35.0

        flows = InventoryFlow.objects.filter(
            goods=product_a,
            type=InventoryFlow.Type.STOCK_CHECK
        )
        assert flows.exists()
        flow = flows.first()
        assert flow.quantity_change == -5.0
        assert flow.quantity_before == 40.0
        assert flow.quantity_after == 35.0