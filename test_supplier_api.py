import pytest
from django.utils import timezone
from rest_framework import status

from apps.data.models import Supplier

from apps.purchase.models import PurchaseOrder, PurchaseGoods
from apps.stock_in.models import StockInOrder, StockInGoods, StockInRecord, StockInRecordGoods
from apps.goods.models import Goods, Inventory


# ==================== Fixtures ====================

@pytest.fixture
def supplier_data(admin_user):
    return {
        'number': 'S001',
        'name': '华为科技',
        'contact': '张经理',
        'phone': '13800138001',
        'email': 'huawei@example.com',
        'address': '深圳市龙岗区坂田华为基地',
        'bank_account': '6222 0200 1234 5678',
        'bank_name': '中国银行深圳分行',
        'remark': '优质供应商',
        'is_active': True,
    }


@pytest.fixture
def supplier_created(api_client, supplier_data):
    url = '/api/suppliers/'
    response = api_client.post(url, supplier_data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


# ==================== Test Class ====================

@pytest.mark.django_db
class TestSupplierAPI:

    def test_create_supplier_success(self, api_client, supplier_data):
        url = '/api/suppliers/'
        response = api_client.post(url, supplier_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data['number'] == supplier_data['number']
        assert data['name'] == supplier_data['name']
        assert data['contact'] == supplier_data['contact']
        assert data['phone'] == supplier_data['phone']
        assert data['email'] == supplier_data['email']
        assert data['address'] == supplier_data['address']
        assert data['bank_account'] == supplier_data['bank_account']
        assert data['bank_name'] == supplier_data['bank_name']
        assert data['remark'] == supplier_data['remark']
        assert data['is_active'] is True

        supplier = Supplier.objects.get(number=supplier_data['number'])
        assert supplier.name == supplier_data['name']

    def test_list_suppliers(self, api_client, supplier_created):
        url = '/api/suppliers/?page=1'
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
        assert 'contact' in item
        assert 'is_active' in item

    def test_update_supplier_partial(self, api_client, supplier_created):
        supplier_id = supplier_created['id']
        url = f'/api/suppliers/{supplier_id}/'
        update_data = {'contact': '李经理'}
        response = api_client.patch(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['contact'] == '李经理'
        assert data['name'] == supplier_created['name']
        assert data['phone'] == supplier_created['phone']

        supplier = Supplier.objects.get(id=supplier_id)
        assert supplier.contact == '李经理'
        assert supplier.name == supplier_created['name']

    def test_delete_supplier(self, api_client, supplier_created):
        supplier_id = supplier_created['id']
        url = f'/api/suppliers/{supplier_id}/'
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        with pytest.raises(Supplier.DoesNotExist):
            Supplier.objects.get(id=supplier_id)

    def test_create_supplier_duplicate_name(self, api_client, supplier_created):
        duplicate_data = {
            'number': 'S002',
            'name': '华为科技',
            'contact': '王经理',
            'phone': '13900139002',
            'email': 'wang@example.com',
        }
        url = '/api/suppliers/'
        response = api_client.post(url, duplicate_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = str(response.data).lower()
        assert '名称' in error_msg or 'name' in error_msg or '已存在' in error_msg or 'exists' in error_msg

    # 验证已被采购入库单引用的供应商禁止删除
    def test_delete_supplier_referenced_by_purchase(
        self, api_client, admin_user, supplier_data, product_a, warehouse_active
    ):
        # ----- 1. 创建一个供应商 -----
        supplier = Supplier.objects.create(
            number=supplier_data['number'],
            name=supplier_data['name'],
            contact=supplier_data['contact'],
            phone=supplier_data['phone'],
            email=supplier_data['email'],
            address=supplier_data['address'],
            bank_account=supplier_data['bank_account'],
            bank_name=supplier_data['bank_name'],
            remark=supplier_data['remark'],
            is_active=supplier_data['is_active'],
            team=admin_user.team,
        )
        supplier_id = supplier.id
        supplier_number = supplier.number

        # ----- 2. 创建采购单并完成入库（引用该供应商） -----
        # 2.1 创建采购单
        purchase_order = PurchaseOrder.objects.create(
            number='PO-REF-001',
            warehouse=warehouse_active,
            supplier=supplier,
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
            number='RK-REF-001',
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
        # 2.4 创建入库记录（模拟已执行入库）
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
        # 2.5 更新库存（确保有库存）
        inventory, _ = Inventory.objects.get_or_create(
            warehouse=warehouse_active,
            goods=product_a,
            team=admin_user.team,
            defaults={'total_quantity': 0.0, 'has_stock': False}
        )
        inventory.total_quantity = 60.0 
        inventory.has_stock = True
        inventory.save()

        # ----- 3. 尝试删除供应商 -----
        delete_url = f'/api/suppliers/{supplier_id}/'
        response = api_client.delete(delete_url)

        # 断言状态码 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST, f"期望400，实际{response.status_code}"

        # 断言错误信息包含“已被采购单据引用”或供应商名称、采购单号等
        error_msg = str(response.data)
        expected_keywords = ['引用', '采购单', 'PO-REF-001']
        assert any(keyword in error_msg for keyword in expected_keywords), \
            f"错误信息未包含预期内容，实际返回：{error_msg}"

        # ----- 4. 验证供应商未被删除 -----
        supplier_exists = Supplier.objects.filter(id=supplier_id).exists()
        assert supplier_exists is True, "供应商记录已被物理删除，但预期应保留（逻辑删除不生效）"

        # 额外检查：供应商的 is_active 未被修改（如果删除接口会改它）
        supplier.refresh_from_db()
        assert supplier.is_active is True, "供应商被误设为非激活状态"