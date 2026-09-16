import pytest
from django.utils import timezone
from rest_framework import status

from apps.data.models import Warehouse
from apps.goods.models import Goods, Inventory
from apps.purchase.models import PurchaseOrder, PurchaseGoods
from apps.stock_in.models import StockInOrder, StockInGoods, StockInRecord, StockInRecordGoods


# ==================== Fixtures ====================

@pytest.fixture
def warehouse_data(admin_user):
    # 创建仓库数据
    return {
        'number': 'W001',
        'name': '北京仓',
        'manager': admin_user.id,
        'phone': '010-88888888',
        'address': '北京市朝阳区望京SOHO',
        'remark': '主仓库',
        'is_active': True,
    }


@pytest.fixture
def warehouse_created(api_client, warehouse_data):
    # 创建一个仓库供后续测试使用
    url = '/api/warehouses/'
    response = api_client.post(url, warehouse_data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


@pytest.fixture
def product_with_stock(db, product_a, warehouse_created, admin_user):
    # 在指定仓库中创建产品A的库存（存量>0）
    warehouse_id = warehouse_created['id']
    warehouse = Warehouse.objects.get(id=warehouse_id)
    inventory, created = Inventory.objects.get_or_create(
        warehouse=warehouse,
        goods=product_a,
        team=admin_user.team,
        defaults={'total_quantity': 10.0, 'has_stock': True}
    )
    if not created:
        inventory.total_quantity = 10.0
        inventory.has_stock = True
        inventory.save()
    return inventory


# ==================== Test Class ====================

@pytest.mark.django_db
class TestWarehouseAPI:

    # ========== TC-API-050 仓库创建接口验证 ==========
    def test_create_warehouse_success(self, api_client, warehouse_data, admin_user, product_a):
        url = '/api/warehouses/'
        response = api_client.post(url, warehouse_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data['number'] == warehouse_data['number']
        assert data['name'] == warehouse_data['name']
        assert data['phone'] == warehouse_data['phone']
        assert data['address'] == warehouse_data['address']
        assert data['remark'] == warehouse_data['remark']
        assert data['is_active'] is True

        warehouse = Warehouse.objects.get(number=warehouse_data['number'])
        assert warehouse.name == warehouse_data['name']
        assert warehouse.address == warehouse_data['address']

        # 验证自动生成库存记录
        inventory_exists = Inventory.objects.filter(
            warehouse=warehouse,
            goods=product_a,
            team=admin_user.team
        ).exists()
        assert inventory_exists, "创建仓库后未自动为产品A生成库存记录"

    # ========== TC-API-051 仓库列表查询接口验证 ==========
    def test_list_warehouses(self, api_client, warehouse_created):
        url = '/api/warehouses/?page=1'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert 'results' in data
        assert 'count' in data
        assert len(data['results']) >= 1

        item = data['results'][0]
        assert 'id' in item
        assert 'number' in item
        assert 'name' in item
        assert 'address' in item
        assert 'is_active' in item

    # ========== TC-API-052 仓库更新接口验证（修改地址） ==========
    def test_update_warehouse_partial(self, api_client, warehouse_created):
        warehouse_id = warehouse_created['id']
        url = f'/api/warehouses/{warehouse_id}/'
        update_data = {'address': '北京市海淀区中关村'}
        response = api_client.patch(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['address'] == '北京市海淀区中关村'
        assert data['name'] == warehouse_created['name']
        assert data['phone'] == warehouse_created['phone']

        warehouse = Warehouse.objects.get(id=warehouse_id)
        assert warehouse.address == '北京市海淀区中关村'
        assert warehouse.name == warehouse_created['name']

    # ========== TC-API-053 仓库删除-存在关联库存时联级删除 ==========
    def test_delete_warehouse_with_stock(self, api_client, warehouse_created, product_with_stock):
        # 仓库中存在库存记录（存量>0），删除仓库。
        warehouse_id = warehouse_created['id']
        url = f'/api/warehouses/{warehouse_id}/'
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        # 验证仓库已被物理删除
        with pytest.raises(Warehouse.DoesNotExist):
            Warehouse.objects.get(id=warehouse_id)
        # 验证关联库存也被级联删除
        with pytest.raises(Inventory.DoesNotExist):
            Inventory.objects.get(id=product_with_stock.id)


    # ========== TC-API-054 仓库删除-存在关联库存时禁止删除 ==========
    def test_delete_warehouse_referenced_by_purchase(
        self, api_client, admin_user, product_a, warehouse_active, supplier_active
    ):
        # ----- 1. 创建一个仓库 -----
        warehouse = Warehouse.objects.create(
            number='W999',
            name='测试仓库',
            manager=admin_user,
            phone='010-88888888',
            address='北京市测试区',
            remark='测试用仓库',
            is_active=True,
            team=admin_user.team,
        )
        warehouse_id = warehouse.id

        # ----- 2. 创建采购单并完成入库（引用该仓库） -----
        # 2.1 创建采购单
        purchase_order = PurchaseOrder.objects.create(
            number='PO-REF-WH-001',
            warehouse=warehouse,
            supplier=supplier_active,
            handler=admin_user,
            handle_time=timezone.now().date(),
            total_quantity=50.0,
            total_amount=5000.0,
            arrears_amount=5000.0,
            creator=admin_user,
            team=admin_user.team,
        )
        # 2.2 创建采购明细
        PurchaseGoods.objects.create(
            purchase_order=purchase_order,
            goods=product_a,
            purchase_quantity=50.0,
            purchase_price=100.0,
            total_amount=5000.0,
            team=admin_user.team,
        )
        # 2.3 创建入库通知单
        stock_in_order = StockInOrder.objects.create(
            number='RK-REF-WH-001',
            warehouse=warehouse,
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
        # 2.4 创建入库记录（模拟已执行入库）
        stock_in_record = StockInRecord.objects.create(
            stock_in_order=stock_in_order,
            warehouse=warehouse,
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

        # ----- 3. 尝试删除被引用的仓库 -----
        delete_url = f'/api/warehouses/{warehouse_id}/'
        response = api_client.delete(delete_url)

        # 断言状态码 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"期望400，实际{response.status_code}"

        # 断言错误信息包含“被引用”或仓库被采购单引用相关提示
        error_msg = str(response.data)
        expected_keywords = ['引用', '采购单', 'PO-REF-WH-001', '仓库已被引用']
        assert any(keyword in error_msg for keyword in expected_keywords), \
            f"错误信息未包含预期内容，实际返回：{error_msg}"

        # ----- 4. 验证仓库未被删除 -----
        warehouse_exists = Warehouse.objects.filter(id=warehouse_id).exists()
        assert warehouse_exists is True, "仓库记录已被删除，但预期应保留"

        # 额外检查：仓库的 is_active 未被修改
        warehouse.refresh_from_db()
        assert warehouse.is_active is True, "仓库被误设为非激活状态"