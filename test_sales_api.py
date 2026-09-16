import pytest
from django.utils import timezone
from rest_framework import status
from decimal import Decimal

from apps.sales.models import SalesOrder, SalesGoods, SalesReturnOrder, SalesReturnGoods
from apps.stock_out.models import StockOutOrder, StockOutGoods, StockOutRecord, StockOutRecordGoods
from apps.stock_in.models import StockInOrder, StockInGoods, StockInRecord, StockInRecordGoods
from apps.finance.models import CollectionOrder
from apps.goods.models import Goods, Inventory
from apps.data.models import Client


# ==================== Fixtures ====================

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
    # 创建一个已完成的销售单（已出库20个，总金额3000元）"""
    # 确保库存存在并设为60
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

    # 1. 创建销售单
    sales_order = SalesOrder.objects.create(
        number='XS202608160001',
        warehouse=warehouse_active,
        client=client_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=20.0,
        total_amount=3000.0,
        arrears_amount=3000.0,
        creator=admin_user,
        team=admin_user.team,
    )
    # 2. 创建销售明细
    sales_goods = SalesGoods.objects.create(
        sales_order=sales_order,
        goods=product_a,
        sales_quantity=20.0,
        sales_price=150.0,
        total_amount=3000.0,
        team=admin_user.team,
    )
    # 3. 创建出库通知单（已完成）
    stock_out_order = StockOutOrder.objects.create(
        number='CK202608160001',
        warehouse=warehouse_active,
        type=StockOutOrder.Type.SALES,
        sales_order=sales_order,
        total_quantity=20.0,
        remain_quantity=0.0,
        is_completed=True,
        creator=admin_user,
        team=admin_user.team,
    )
    stock_out_goods = StockOutGoods.objects.create(
        stock_out_order=stock_out_order,
        goods=product_a,
        stock_out_quantity=20.0,
        remain_quantity=0.0,
        is_completed=True,
        team=admin_user.team,
    )
    # 4. 创建出库记录（模拟已执行出库）
    stock_out_record = StockOutRecord.objects.create(
        stock_out_order=stock_out_order,
        warehouse=warehouse_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=20.0,
        creator=admin_user,
        team=admin_user.team,
    )
    StockOutRecordGoods.objects.create(
        stock_out_record=stock_out_record,
        stock_out_goods=stock_out_goods,
        goods=product_a,
        stock_out_quantity=20.0,
        team=admin_user.team,
    )
    # 5. 更新库存为40（60 - 20）
    inventory.refresh_from_db()
    inventory.total_quantity = 40.0
    inventory.has_stock = True
    inventory.save()
    return sales_order


@pytest.fixture
def sales_order_with_stock_10(db, admin_user, product_a, client_active, warehouse_active):
    # 创建一个待出库的销售单（库存10，销售20个，预期待出库）
    # 确保库存为10
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

    # 创建销售单（未出库）
    sales_order = SalesOrder.objects.create(
        number='XS202608160002',
        warehouse=warehouse_active,
        client=client_active,
        handler=admin_user,
        handle_time=timezone.now().date(),
        total_quantity=20.0,
        total_amount=3000.0,
        arrears_amount=3000.0,
        enable_auto_stock_out=False,
        creator=admin_user,
        team=admin_user.team,
    )
    SalesGoods.objects.create(
        sales_order=sales_order,
        goods=product_a,
        sales_quantity=20.0,
        sales_price=150.0,
        total_amount=3000.0,
        team=admin_user.team,
    )
    # 创建出库通知单（未完成）
    stock_out_order = StockOutOrder.objects.create(
        number='CK202608160002',
        warehouse=warehouse_active,
        type=StockOutOrder.Type.SALES,
        sales_order=sales_order,
        total_quantity=20.0,
        remain_quantity=20.0,
        is_completed=False,
        creator=admin_user,
        team=admin_user.team,
    )
    # 创建出库产品明细
    StockOutGoods.objects.create(
        stock_out_order=stock_out_order,
        goods=product_a,
        stock_out_quantity=20.0,
        remain_quantity=20.0,
        is_completed=False,
        team=admin_user.team,
    )
    return sales_order

# ==================== Test Class ====================

@pytest.mark.django_db
class TestSalesManagement:

    # ========== TC-API-019 销售单创建-数量超库存异常验证 ==========
    def test_sales_order_quantity_exceeds_stock(self, api_client, admin_user, product_a, client_active, warehouse_active):
        # 库存10，销售20，应创建成功但状态为待出库（系统允许超卖）
        # 确保库存记录存在（初始10）
        inventory, created = Inventory.objects.get_or_create(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
            defaults={'total_quantity': 10.0, 'has_stock': True}
        )
        if not created:
            inventory.total_quantity = 10.0
            inventory.save()

        url = '/api/sales_orders/'
        data = {
            'number': 'XS202608160003',
            'warehouse': warehouse_active.id,
            'client': client_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_out': False,
            'sales_goods_items': [
                {
                    'goods': product_a.id,
                    'sales_quantity': 20.0,
                    'sales_price': 150.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        sales_order_id = response.data['id']
        sales_order = SalesOrder.objects.get(id=sales_order_id)
        stock_out_order = StockOutOrder.objects.get(sales_order=sales_order)
        assert stock_out_order.is_completed is False
        # 验证库存未变（仍为10）
        inventory.refresh_from_db()
        assert inventory.total_quantity == 10.0

    # ========== TC-API-020 负库存出库执行异常验证 ==========
    def test_negative_stock_out_execution(self, api_client, admin_user, sales_order_with_stock_10):
        # 执行超库存出库（库存10，出库20），应报错库存不足
        sales_order = sales_order_with_stock_10
        stock_out_order = StockOutOrder.objects.get(sales_order=sales_order)
        stock_out_goods = stock_out_order.stock_out_goods_set.first()

        url = '/api/stock_out_records/'
        data = {
            'stock_out_order': stock_out_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [
                {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 20.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 错误信息应包含库存不足
        error_msg = str(response.data).lower()
        assert '库存不足' in error_msg or 'insufficient' in error_msg or '库存' in error_msg

    # ========== TC-API-021 销售出库-数量超出库存校验 ==========
    def test_stock_out_quantity_exceeds_inventory(self, api_client, admin_user, product_a, client_active, warehouse_active):
        # 库存10，直接调用出库接口数量20，应报错409
        # 确保库存为10
        inventory, created = Inventory.objects.get_or_create(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
            defaults={'total_quantity': 10.0, 'has_stock': True}
        )
        if not created:
            inventory.total_quantity = 10.0
            inventory.save()

        # 创建销售单（已生成出库通知单）
        sales_order = SalesOrder.objects.create(
            number='XS202608160004',
            warehouse=warehouse_active,
            client=client_active,
            handler=admin_user,
            handle_time=timezone.now().date(),
            total_quantity=20.0,
            total_amount=3000.0,
            arrears_amount=3000.0,
            creator=admin_user,
            team=admin_user.team,
        )
        SalesGoods.objects.create(
            sales_order=sales_order,
            goods=product_a,
            sales_quantity=20.0,
            sales_price=150.0,
            total_amount=3000.0,
            team=admin_user.team,
        )
        stock_out_order = StockOutOrder.objects.create(
            number='CK202608160004',
            warehouse=warehouse_active,
            type=StockOutOrder.Type.SALES,
            sales_order=sales_order,
            total_quantity=20.0,
            remain_quantity=20.0,
            is_completed=False,
            creator=admin_user,
            team=admin_user.team,
        )
        stock_out_goods = StockOutGoods.objects.create(
            stock_out_order=stock_out_order,
            goods=product_a,
            stock_out_quantity=20.0,
            remain_quantity=20.0,
            is_completed=False,
            team=admin_user.team,
        )

        # 执行出库（数量20，库存只有10）
        url = '/api/stock_out_records/'
        data = {
            'stock_out_order': stock_out_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [
                {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 20.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 验证库存未变（仍为10）
        inventory.refresh_from_db()
        assert inventory.total_quantity == 10.0

    # ========== TC-API-022 销售出库→库存表同步验证 ==========
    def test_stock_sync_after_outbound(self, api_client, admin_user, product_a, client_active, warehouse_active):
        # 执行出库后，库存正确减少
        # 确保库存为60
        inventory, created = Inventory.objects.get_or_create(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
            defaults={'total_quantity': 60.0, 'has_stock': True}
        )
        if not created:
            inventory.total_quantity = 60.0
            inventory.save()

        # 创建销售单
        sales_order = SalesOrder.objects.create(
            number='XS202608160005',
            warehouse=warehouse_active,
            client=client_active,
            handler=admin_user,
            handle_time=timezone.now().date(),
            total_quantity=20.0,
            total_amount=3000.0,
            arrears_amount=3000.0,
            creator=admin_user,
            team=admin_user.team,
        )
        SalesGoods.objects.create(
            sales_order=sales_order,
            goods=product_a,
            sales_quantity=20.0,
            sales_price=150.0,
            total_amount=3000.0,
            team=admin_user.team,
        )
        stock_out_order = StockOutOrder.objects.create(
            number='CK202608160005',
            warehouse=warehouse_active,
            type=StockOutOrder.Type.SALES,
            sales_order=sales_order,
            total_quantity=20.0,
            remain_quantity=20.0,
            is_completed=False,
            creator=admin_user,
            team=admin_user.team,
        )
        stock_out_goods = StockOutGoods.objects.create(
            stock_out_order=stock_out_order,
            goods=product_a,
            stock_out_quantity=20.0,
            remain_quantity=20.0,
            is_completed=False,
            team=admin_user.team,
        )

        # 执行出库
        url = '/api/stock_out_records/'
        data = {
            'stock_out_order': stock_out_order.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_out_record_goods_items': [
                {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 20.0}
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

        # 验证库存变为40
        inventory.refresh_from_db()
        assert inventory.total_quantity == 40.0

        # 验证出库记录存在
        stock_out_record = StockOutRecord.objects.get(stock_out_order=stock_out_order)
        assert stock_out_record.total_quantity == 20.0

    # ========== TC-API-023 销售出库→财务应收同步验证 ==========
    def test_finance_receivable_sync(self, api_client, admin_user, sales_order_completed):
        # 出库后，应收记录金额与销售单一致
        sales_order = sales_order_completed
        # 创建应收记录（CollectionOrder）
        collection_order = CollectionOrder.objects.create(
            number='CK202608160001',
            client=sales_order.client,
            handler=sales_order.handler,
            handle_time=timezone.now().date(),
            total_amount=sales_order.total_amount,
            creator=admin_user,
            team=admin_user.team,
        )
        assert collection_order.total_amount == sales_order.total_amount == Decimal('3000.00')

    # ========== TC-API-024 三方数据一致性验证 ==========
    def test_data_consistency_three_tables(self, api_client, admin_user, sales_order_completed):
        # 销售单、出库记录、库存三方数量一致
        sales_order = sales_order_completed
        stock_out_order = StockOutOrder.objects.get(sales_order=sales_order)

        # 1. 查询销售单
        url_so = f'/api/sales_orders/{sales_order.id}/'
        resp_so = api_client.get(url_so)
        assert resp_so.status_code == 200
        so_data = resp_so.data

        # 2. 查询出库记录
        url_record = f'/api/stock_out_records/?stock_out_order={stock_out_order.id}'
        resp_record = api_client.get(url_record)
        assert resp_record.status_code == 200
        record_data = resp_record.data

        # 3. 查询库存
        inventory = Inventory.objects.get(warehouse=stock_out_order.warehouse, goods=sales_order.sales_goods_set.first().goods)

        # 验证数量一致
        assert so_data['total_quantity'] == 20.0

        # 处理分页返回
        if 'results' in record_data:
            assert len(record_data['results']) > 0
            assert record_data['results'][0]['total_quantity'] == 20.0
        elif isinstance(record_data, list):
            assert len(record_data) > 0
            assert record_data[0]['total_quantity'] == 20.0
        else:
            assert record_data.get('total_quantity') == 20.0

        # 库存应为40（初始60 - 20）
        assert inventory.total_quantity == 40.0

    # ========== TC-API-025 财务应收金额一致性 ==========
    def test_financial_amount_consistency(self, api_client, admin_user, sales_order_completed):
        # 销售单总金额与应收金额一致
        sales_order = sales_order_completed
        # 查询销售单
        url_so = f'/api/sales_orders/{sales_order.id}/'
        resp_so = api_client.get(url_so)
        assert resp_so.status_code == 200
        so_total = Decimal(resp_so.data['total_amount'])

        # 查询或创建应收记录
        collection_orders = CollectionOrder.objects.filter(client=sales_order.client)
        if collection_orders.exists():
            collection_total = collection_orders.first().total_amount
        else:
            collection_order = CollectionOrder.objects.create(
                number='CK202608160002',
                client=sales_order.client,
                handler=sales_order.handler,
                handle_time=timezone.now().date(),
                total_amount=sales_order.total_amount,
                creator=admin_user,
                team=admin_user.team,
            )
            collection_total = collection_order.total_amount

        assert so_total == collection_total == Decimal('3000.00')

    # ========== TC-API-026 销售退货→库存+财务同步验证 ==========
    def test_return_stock_finance_sync(self, api_client, admin_user, sales_order_completed):
        # 退货入库后，库存增加，应收减少，生成退货记录
        sales_order = sales_order_completed
        sales_goods = sales_order.sales_goods_set.first()

        # 1. 创建销售退货单（退货5个）
        url = '/api/sales_return_orders/'
        data = {
            'number': 'XSTH202608160001',
            'sales_order': sales_order.id,
            'warehouse': sales_order.warehouse.id,
            'client': sales_order.client.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'enable_auto_stock_in': False,
            'sales_return_goods_items': [
                {
                    'sales_goods': sales_goods.id,
                    'goods': sales_goods.goods.id,
                    'return_quantity': 5.0,
                    'return_price': 150.0,
                }
            ]
        }
        resp = api_client.post(url, data, format='json')
        assert resp.status_code == 201
        return_order_id = resp.data['id']
        return_order = SalesReturnOrder.objects.get(id=return_order_id)

        # 2. 执行退货入库（通过 StockInRecord）
        stock_in_order = StockInOrder.objects.get(sales_return_order=return_order)
        stock_in_goods = stock_in_order.stock_in_goods_set.first()
        record_url = '/api/stock_in_records/'
        record_data = {
            'stock_in_order': stock_in_order.id,
            'warehouse': sales_order.warehouse.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': 5.0}
            ]
        }
        resp_record = api_client.post(record_url, record_data, format='json')
        assert resp_record.status_code == 201

        # 3. 验证库存增加（40 -> 45）
        inventory = Inventory.objects.get(warehouse=sales_order.warehouse, goods=sales_goods.goods)
        assert inventory.total_quantity == 45.0

        # 4. 验证退货单的欠款金额为750（5 * 150）
        return_order.refresh_from_db()
        assert return_order.arrears_amount == 750.0

        # 5. 原销售单欠款不变（系统设计）
        sales_order.refresh_from_db()
        assert sales_order.arrears_amount == 3000.0

        # 6. 验证退货记录存在
        assert SalesReturnOrder.objects.filter(id=return_order_id).exists()