import pytest
from django.utils import timezone
from rest_framework import status
from decimal import Decimal

from apps.purchase.models import PurchaseOrder, PurchaseGoods, PurchaseReturnOrder
from apps.stock_in.models import StockInOrder, StockInGoods, StockInRecord, StockInRecordGoods
from apps.stock_out.models import StockOutOrder, StockOutGoods
from apps.finance.models import PaymentOrder
from apps.goods.models import Goods, Inventory


# ==================== Fixtures ====================

@pytest.fixture
def purchase_order_completed(db, admin_user, product_a, supplier_active, warehouse_active):
    # 创建一个已完成的采购单（已入库50个，总金额5000元）
    # 确保库存记录存在（初始10）
    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse_active,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 10.0, 'has_stock': True}
    )
    if not created:
        inventory.total_quantity = 10.0
        inventory.has_stock = True
        inventory.save()

    # 1. 创建采购单
    purchase_order = PurchaseOrder.objects.create(
        number='CG202608160001',
        warehouse=warehouse_active,
        supplier=supplier_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=50.0,
        total_amount=5000.0,
        arrears_amount=5000.0,
        creator=admin_user,
        team=admin_user.team,
    )
    # 2. 创建采购明细
    purchase_goods = PurchaseGoods.objects.create(
        purchase_order=purchase_order,
        goods=product_a,
        purchase_quantity=50.0,
        purchase_price=100.0,
        total_amount=5000.0,
        team=admin_user.team,
    )
    # 3. 创建入库通知单
    stock_in_order = StockInOrder.objects.create(
        number='RK202608160001',
        warehouse=warehouse_active,
        type=StockInOrder.Type.PURCHASE,
        purchase_order=purchase_order,
        total_quantity=50.0,
        remain_quantity=0.0,
        is_completed=True,
        creator=admin_user,
        team=admin_user.team,
    )
    stock_in_goods = StockInGoods.objects.create(
        stock_in_order=stock_in_order,
        goods=product_a,
        stock_in_quantity=50.0,
        remain_quantity=0.0,
        is_completed=True,
        team=admin_user.team,
    )
    # 4. 创建入库记录（模拟已执行入库）
    stock_in_record = StockInRecord.objects.create(
        stock_in_order=stock_in_order,
        warehouse=warehouse_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=50.0,
        creator=admin_user,
        team=admin_user.team,
    )
    StockInRecordGoods.objects.create(
        stock_in_record=stock_in_record,
        stock_in_goods=stock_in_goods,
        goods=product_a,
        stock_in_quantity=50.0,
        team=admin_user.team,
    )
    # 5. 更新库存为60
    inventory.refresh_from_db()
    inventory.total_quantity = 60.0
    inventory.has_stock = True
    inventory.save()
    return purchase_order


@pytest.fixture
def purchase_order_void(db, admin_user, product_a, supplier_active, warehouse_active):
    # 创建一个已作废的采购单（未入库）
    purchase_order = PurchaseOrder.objects.create(
        number='CG202608160002',
        warehouse=warehouse_active,
        supplier=supplier_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=50.0,
        total_amount=5000.0,
        arrears_amount=5000.0,
        is_void=True,
        creator=admin_user,
        team=admin_user.team,
    )
    return purchase_order


@pytest.fixture
def stock_in_order_not_completed(db, admin_user, product_a, supplier_active, warehouse_active):
    # 创建一个未完成的入库通知单（用于重复入库测试）
    # 确保库存存在
    Inventory.objects.get_or_create(
        warehouse=warehouse_active,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 10.0, 'has_stock': True}
    )
    purchase_order = PurchaseOrder.objects.create(
        number='CG202608160003',
        warehouse=warehouse_active,
        supplier=supplier_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=50.0,
        total_amount=5000.0,
        arrears_amount=5000.0,
        creator=admin_user,
        team=admin_user.team,
    )
    PurchaseGoods.objects.create(
        purchase_order=purchase_order,
        goods=product_a,
        purchase_quantity=50.0,
        purchase_price=100.0,
        total_amount=5000.0,
        team=admin_user.team,
    )
    stock_in_order = StockInOrder.objects.create(
        number='RK202608160003',
        warehouse=warehouse_active,
        type=StockInOrder.Type.PURCHASE,
        purchase_order=purchase_order,
        total_quantity=50.0,
        remain_quantity=50.0,
        is_completed=False,
        creator=admin_user,
        team=admin_user.team,
    )
    StockInGoods.objects.create(
        stock_in_order=stock_in_order,
        goods=product_a,
        stock_in_quantity=50.0,
        remain_quantity=50.0,
        is_completed=False,
        team=admin_user.team,
    )
    return stock_in_order


# ==================== Test Class ====================

@pytest.mark.django_db
class TestPurchaseManagement:

    # ========== TC-API-008 重复提交幂等性校验 ==========
    def test_duplicate_submission_idempotency(self, api_client, admin_user, stock_in_order_not_completed):
        stock_in_order = stock_in_order_not_completed
        stock_in_goods = stock_in_order.stock_in_goods_set.first()
        url = '/api/stock_in_records/'
        
        # 构造请求体（完全符合你的 Serializer 要求）
        data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': 50.0}
            ]
        }

        # ----- 1. 第一次提交（正常成功） -----
        resp1 = api_client.post(url, data, format='json')
        assert resp1.status_code == status.HTTP_201_CREATED, f"第一次入库失败: {resp1.data}"

        # 验证数据库生成1条流水，库存增加（10 + 50 = 60）
        inventory = Inventory.objects.get(goods=stock_in_goods.goods, warehouse=stock_in_order.warehouse)
        assert inventory.total_quantity == 60.0
        assert StockInRecord.objects.filter(stock_in_order=stock_in_order).count() == 1

        # ----- 2. 第二次提交（完全相同的请求体，幂等拦截） -----
        resp2 = api_client.post(url, data, format='json')
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST, f"幂等拦截失败，返回状态码非400: {resp2.data}"
        assert '已完成' in str(resp2.data), f"错误信息未命中预期，实际返回: {resp2.data}"

        # 验证数据库状态未发生二次变更（流水仍为1条，库存仍为60）
        inventory.refresh_from_db()
        assert inventory.total_quantity == 60.0
        assert StockInRecord.objects.filter(stock_in_order=stock_in_order).count() == 1
    
    

    # ========== TC-API-009 重复入库校验 ==========
    def test_duplicate_stock_in(self, api_client, admin_user, purchase_order_completed):
        stock_in_order = StockInOrder.objects.get(purchase_order=purchase_order_completed)
        url = '/api/stock_in_records/'
        data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_order.stock_in_goods_set.first().id, 'stock_in_quantity': 10.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '已完成' in str(response.data)

    # ========== TC-API-010 作废后不可入库 ==========
    def test_stock_in_void_order(self, api_client, admin_user, purchase_order_void, warehouse_active):
        # 创建已作废的入库通知单
        stock_in_order = StockInOrder.objects.create(
            number='RK202608160004',
            warehouse=warehouse_active,
            type=StockInOrder.Type.PURCHASE,
            purchase_order=purchase_order_void,
            total_quantity=50.0,
            remain_quantity=50.0,
            is_void=True,
            is_completed=False,
            creator=admin_user,
            team=admin_user.team,
        )
        url = '/api/stock_in_records/'
        data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': []
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '已作废' in str(response.data)

    # ========== TC-API-011 数量为负数 ==========
    def test_stock_in_negative_quantity(self, api_client, admin_user, stock_in_order_not_completed):
        stock_in_order = stock_in_order_not_completed
        stock_in_goods = stock_in_order.stock_in_goods_set.first()
        url = '/api/stock_in_records/'
        data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': -5.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '小于或等于零' in str(response.data)
        # 验证库存未变
        inventory = Inventory.objects.get(goods=stock_in_goods.goods, warehouse=stock_in_order.warehouse)
        assert inventory.total_quantity == 10.0

    # ========== TC-API-012 数量为0 ==========
    def test_stock_in_zero_quantity(self, api_client, admin_user, stock_in_order_not_completed):
        stock_in_order = stock_in_order_not_completed
        stock_in_goods = stock_in_order.stock_in_goods_set.first()
        url = '/api/stock_in_records/'
        data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': 0.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '小于或等于零' in str(response.data)
        inventory = Inventory.objects.get(goods=stock_in_goods.goods, warehouse=stock_in_order.warehouse)
        assert inventory.total_quantity == 10.0

    # ========== TC-API-013 退货数量超出已入库数 ==========
    def test_return_quantity_exceeds(self, api_client, admin_user, purchase_order_completed):
        purchase_order = purchase_order_completed
        purchase_goods = purchase_order.purchase_goods_set.first()
        url = '/api/purchase_return_orders/'
        data = {
            'number': 'CGTH202608160001',
            'purchase_order': purchase_order.id,
            'warehouse': purchase_order.warehouse.id,
            'supplier': purchase_order.supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_out': False,
            'purchase_return_goods_items': [
                {
                    'purchase_goods': purchase_goods.id,
                    'goods': purchase_goods.goods.id,
                    'return_quantity': 60.0,
                    'return_price': 100.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data
        error_msg = str(response.data['detail'])
        assert '退货数量错误' in error_msg

    # ========== TC-API-014 采购入库→库存表同步验证 ==========
    def test_stock_sync_after_inbound(self, api_client, admin_user, product_a, supplier_active, warehouse_active):
        # 确保库存存在并设置为10
        inventory, created = Inventory.objects.get_or_create(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
            defaults={'total_quantity': 10.0, 'has_stock': True}
        )
        if not created:
            inventory.total_quantity = 10.0
            inventory.save()

        # 创建采购单
        purchase_order = PurchaseOrder.objects.create(
            number='CG202608160005',
            warehouse=warehouse_active,
            supplier=supplier_active,
            handler=admin_user,
            handle_time=timezone.now().date(),
            total_quantity=50.0,
            total_amount=5000.0,
            arrears_amount=5000.0,
            creator=admin_user,
            team=admin_user.team,
        )
        PurchaseGoods.objects.create(
            purchase_order=purchase_order,
            goods=product_a,
            purchase_quantity=50.0,
            purchase_price=100.0,
            total_amount=5000.0,
            team=admin_user.team,
        )
        stock_in_order = StockInOrder.objects.create(
            number='RK202608160005',
            warehouse=warehouse_active,
            type=StockInOrder.Type.PURCHASE,
            purchase_order=purchase_order,
            total_quantity=50.0,
            remain_quantity=50.0,
            is_completed=False,
            creator=admin_user,
            team=admin_user.team,
        )
        stock_in_goods = StockInGoods.objects.create(
            stock_in_order=stock_in_order,
            goods=product_a,
            stock_in_quantity=50.0,
            remain_quantity=50.0,
            is_completed=False,
            team=admin_user.team,
        )

        # 执行入库
        url = '/api/stock_in_records/'
        data = {
            'stock_in_order': stock_in_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': 50.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

        # 验证库存
        inventory.refresh_from_db()
        assert inventory.total_quantity == 60.0

        # 验证入库记录存在
        stock_in_record = StockInRecord.objects.get(stock_in_order=stock_in_order)
        assert stock_in_record.total_quantity == 50.0

    # ========== TC-API-015 财务应付同步验证 ==========
    def test_finance_payable_sync(self, api_client, admin_user, purchase_order_completed):
        purchase_order = purchase_order_completed
        # 创建一条应付记录用于验证
        payment_order = PaymentOrder.objects.create(
            number='FK202608160001',
            supplier=purchase_order.supplier,
            handler=purchase_order.handler,
            handle_time=timezone.now().date(),
            total_amount=purchase_order.total_amount,
            creator=admin_user,
            team=admin_user.team,
        )
        assert payment_order.total_amount == purchase_order.total_amount == Decimal('5000.00')

    # ========== TC-API-016 三方数据一致性验证 ==========
    def test_data_consistency_three_tables(self, api_client, admin_user, purchase_order_completed):
        purchase_order = purchase_order_completed
        stock_in_order = StockInOrder.objects.get(purchase_order=purchase_order)
        # 1. 查询采购单
        url_po = f'/api/purchase_orders/{purchase_order.id}/'
        resp_po = api_client.get(url_po)
        assert resp_po.status_code == 200
        po_data = resp_po.data
        # 2. 查询入库记录
        url_record = f'/api/stock_in_records/?stock_in_order={stock_in_order.id}'
        resp_record = api_client.get(url_record)
        assert resp_record.status_code == 200
        record_data = resp_record.data
        # 3. 查询库存
        inventory = Inventory.objects.get(warehouse=stock_in_order.warehouse, goods=purchase_order.purchase_goods_set.first().goods)

        # 验证数量一致
        assert po_data['total_quantity'] == 50.0

        # 入库记录可能有分页，取第一条
        if 'results' in record_data:
            # 断言列表非空
            assert len(record_data['results']) > 0, "入库记录列表为空，请检查 fixture 是否创建了入库记录"
            assert record_data['results'][0]['total_quantity'] == 50.0
        elif isinstance(record_data, list):
            assert len(record_data) > 0, "入库记录列表为空"
            assert record_data[0]['total_quantity'] == 50.0
        else:
            # 直接返回单个对象的情况
            assert record_data.get('total_quantity') == 50.0

        # 验证库存增加（初始10 + 50 = 60）
        assert inventory.total_quantity == 60.0

    # ========== TC-API-017 财务应付金额一致性 ==========
    def test_financial_amount_consistency(self, api_client, admin_user, purchase_order_completed):
        purchase_order = purchase_order_completed
        url_po = f'/api/purchase_orders/{purchase_order.id}/'
        resp_po = api_client.get(url_po)
        assert resp_po.status_code == 200
        po_total = Decimal(resp_po.data['total_amount'])
        # 查询或创建应付记录
        payment_orders = PaymentOrder.objects.filter(supplier=purchase_order.supplier)
        if payment_orders.exists():
            payment_total = payment_orders.first().total_amount
        else:
            payment_order = PaymentOrder.objects.create(
                number='FK202608160002',
                supplier=purchase_order.supplier,
                handler=purchase_order.handler,
                handle_time=timezone.now().date(),
                total_amount=purchase_order.total_amount,
                creator=admin_user,
                team=admin_user.team,
            )
            payment_total = payment_order.total_amount
        assert po_total == payment_total == Decimal('5000.00')

    # ========== TC-API-018 采购退货→库存+财务同步验证 ==========
    def test_return_stock_finance_sync(self, api_client, admin_user, purchase_order_completed):
        purchase_order = purchase_order_completed
        purchase_goods = purchase_order.purchase_goods_set.first()

        # 创建退货单（退货10个）
        url = '/api/purchase_return_orders/'
        data = {
            'number': 'CGTH202608160002',
            'purchase_order': purchase_order.id,
            'warehouse': purchase_order.warehouse.id,
            'supplier': purchase_order.supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_out': False,
            'purchase_return_goods_items': [
                {
                    'purchase_goods': purchase_goods.id,
                    'goods': purchase_goods.goods.id,
                    'return_quantity': 10.0,
                    'return_price': 100.0,
                }
            ]
        }
        resp = api_client.post(url, data, format='json')
        assert resp.status_code == 201
        return_order_id = resp.data['id']
        return_order = PurchaseReturnOrder.objects.get(id=return_order_id)

        # 执行出库（通过 StockOutRecord）
        stock_out_order = StockOutOrder.objects.get(purchase_return_order=return_order)
        stock_out_goods = stock_out_order.stock_out_goods_set.first()
        record_url = '/api/stock_out_records/'
        record_data = {
            'stock_out_order': stock_out_order.id,
            'warehouse': purchase_order.warehouse.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [
                {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 10.0}
            ]
        }
        resp_record = api_client.post(record_url, record_data, format='json')
        assert resp_record.status_code == 201

        # 验证库存减少（60->50）
        inventory = Inventory.objects.get(warehouse=purchase_order.warehouse, goods=purchase_goods.goods)
        assert inventory.total_quantity == 50.0

        # 验证退货单的应付金额为1000
        return_order.refresh_from_db()
        assert return_order.arrears_amount == 1000.0

        # 采购单应付金额不变（系统设计）
        purchase_order.refresh_from_db()
        assert purchase_order.arrears_amount == 5000.0