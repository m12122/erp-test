import pytest
from django.utils import timezone
from rest_framework import status
from datetime import timedelta
from django.db import models

from apps.flow.models import InventoryFlow
from apps.goods.models import Goods, Inventory
from apps.data.models import Warehouse


# ==================== Fixtures ====================

@pytest.fixture
def test_warehouse(db, admin_user):
    # 创建测试仓库
    return Warehouse.objects.create(
        number='W999',
        name='测试仓库',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def test_product(db, admin_user):
    # 创建测试产品
    return Goods.objects.create(
        number='P999',
        name='测试产品',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def test_inventory(db, test_product, test_warehouse, admin_user):
    # 创建库存记录，初始库存 100
    inventory, created = Inventory.objects.get_or_create(
        warehouse=test_warehouse,
        goods=test_product,
        team=admin_user.team,
        defaults={
            'total_quantity': 100.0,
            'initial_quantity': 100.0,
            'has_stock': True,
        }
    )
    if not created:
        inventory.total_quantity = 100.0
        inventory.initial_quantity = 100.0
        inventory.has_stock = True
        inventory.save()
    return inventory


@pytest.fixture
def product_a_with_flows(db, test_inventory, test_product, test_warehouse, admin_user):
    # 为产品创建多条库存流水记录（直接创建 InventoryFlow），
    # 所有记录的 create_time 都会是当前时间（auto_now_add=True）
    # 创建三条流水（入库、出库、退货）
    InventoryFlow.objects.create(
        warehouse=test_warehouse,
        goods=test_product,
        type=InventoryFlow.Type.PURCHASE,
        quantity_before=100.0,
        quantity_change=50.0,
        quantity_after=150.0,
        creator=admin_user,
        team=admin_user.team,
    )
    InventoryFlow.objects.create(
        warehouse=test_warehouse,
        goods=test_product,
        type=InventoryFlow.Type.SALES,
        quantity_before=150.0,
        quantity_change=30.0,
        quantity_after=120.0,
        creator=admin_user,
        team=admin_user.team,
    )
    InventoryFlow.objects.create(
        warehouse=test_warehouse,
        goods=test_product,
        type=InventoryFlow.Type.PURCHASE_RETURN,
        quantity_before=120.0,
        quantity_change=10.0,
        quantity_after=110.0,
        creator=admin_user,
        team=admin_user.team,
    )

    # 更新库存为最终值 110
    inventory = test_inventory
    inventory.total_quantity = 110.0
    inventory.save()

    return inventory, test_product


# ==================== Test Class ====================

@pytest.mark.django_db
class TestInventoryFlow:

    # ========== TC-API-032 库存流水查询接口验证 ==========
    def test_inventory_flow_query(self, api_client, admin_user, product_a_with_flows):
        inventory, product = product_a_with_flows
        url = f'/api/inventory_flows/?goods={product.id}'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        if 'results' in data:
            flows = data['results']
        else:
            flows = data

        assert len(flows) >= 3

        # 验证按时间倒序（如果有多条记录且时间不同）
        if len(flows) > 1:
            create_times = [f.get('create_time') for f in flows]
            for i in range(len(create_times) - 1):
                assert create_times[i] >= create_times[i+1]

        # 验证必要字段
        for flow in flows:
            assert 'goods' in flow
            assert 'type_display' in flow
            assert 'quantity_change' in flow

    # ========== TC-API-033 库存流水按时间范围筛选验证 ==========
    def test_inventory_flow_time_range(self, api_client, admin_user, product_a_with_flows):
        inventory, product = product_a_with_flows
        now = timezone.now()

        # 测试范围1：未来日期（明天到后天），应返回 0 条
        start = (now + timedelta(days=1)).date()
        end = (now + timedelta(days=2)).date()
        url = f'/api/inventory_flows/?goods={product.id}&start_date={start}&end_date={end}'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        if 'results' in data:
            flows = data['results']
        else:
            flows = data
        assert len(flows) == 0, f"期望0条，实际{len(flows)}条"

        # 测试范围2：包含所有记录（今天-1天 到 明天）
        start_all = (now - timedelta(days=1)).date()
        end_all = (now + timedelta(days=1)).date()
        url = f'/api/inventory_flows/?goods={product.id}&start_date={start_all}&end_date={end_all}'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        if 'results' in data:
            flows_all = data['results']
        else:
            flows_all = data
        assert len(flows_all) >= 3, f"期望至少3条，实际{len(flows_all)}条"

    # ========== TC-API-034 库存流水-出入库汇总一致性验证 ==========
    def test_inventory_flow_summary(self, api_client, admin_user, product_a_with_flows):
        inventory, product = product_a_with_flows

        # 汇总入库类型
        in_types = ['purchase', 'stock_in', 'sales_return', 'stock_transfer_in']
        in_total = InventoryFlow.objects.filter(
            goods=product,
            type__in=in_types
        ).aggregate(total=models.Sum('quantity_change'))['total'] or 0

        # 汇总出库类型
        out_types = ['sales', 'stock_out', 'purchase_return', 'stock_transfer_out']
        out_total = InventoryFlow.objects.filter(
            goods=product,
            type__in=out_types
        ).aggregate(total=models.Sum('quantity_change'))['total'] or 0

        initial_stock = inventory.initial_quantity
        current_stock = inventory.total_quantity
        expected = initial_stock + in_total - out_total

        assert current_stock == expected, \
            f"当前库存 {current_stock} != 初始 {initial_stock} + 入库 {in_total} - 出库 {out_total} = {expected}"