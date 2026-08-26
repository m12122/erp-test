import pytest
from django.utils import timezone
from rest_framework import status

from apps.data.models import Warehouse
from apps.goods.models import Goods, Inventory


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

    # ========== TC-API-044 仓库创建接口验证 ==========
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

    # ========== TC-API-045 仓库列表查询接口验证 ==========
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

    # ========== TC-API-046 仓库更新接口验证（修改地址） ==========
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

    # ========== TC-API-047 仓库删除-存在关联库存时联级删除 ==========
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