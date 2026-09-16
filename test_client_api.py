import pytest
from django.utils import timezone
from rest_framework import status

from apps.data.models import Client
from apps.sales.models import SalesOrder, SalesGoods
from apps.stock_out.models import StockOutOrder, StockOutGoods, StockOutRecord, StockOutRecordGoods


# ==================== Fixtures ====================

@pytest.fixture
def client_data(admin_user):
    # 有效客户创建数据
    return {
        'number': 'C001',
        'name': '华为技术有限公司',
        'level': '1',
        'contact': '张经理',
        'phone': '13800138001',
        'email': 'huawei@example.com',
        'address': '深圳市龙岗区坂田华为基地',
        'remark': '重要客户',
        'is_active': True,
    }


@pytest.fixture
def client_created(api_client, client_data):
    # 创建一个客户供后续测试使用
    url = '/api/clients/'
    response = api_client.post(url, client_data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


# ==================== Test Class ====================

@pytest.mark.django_db
class TestClientAPI:

    # ========== TC-API-044 客户创建接口验证 ==========
    def test_create_client_success(self, api_client, client_data):
        url = '/api/clients/'
        response = api_client.post(url, client_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data['number'] == client_data['number']
        assert data['name'] == client_data['name']
        assert data['level'] == client_data['level']
        assert data['contact'] == client_data['contact']
        assert data['phone'] == client_data['phone']
        assert data['email'] == client_data['email']
        assert data['address'] == client_data['address']
        assert data['remark'] == client_data['remark']
        assert data['is_active'] is True

        client = Client.objects.get(number=client_data['number'])
        assert client.name == client_data['name']
        assert client.contact == client_data['contact']
        assert client.level == client_data['level']

    # ========== TC-API-045 客户列表查询接口验证 ==========
    def test_list_clients(self, api_client, client_created):
        url = '/api/clients/?page=1'
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
        assert 'level' in item
        assert 'is_active' in item

    # ========== TC-API-046 客户更新接口验证（修改电话） ==========
    def test_update_client_partial(self, api_client, client_created):
        client_id = client_created['id']
        url = f'/api/clients/{client_id}/'
        update_data = {'phone': '13900139002'}
        response = api_client.patch(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['phone'] == '13900139002'
        assert data['name'] == client_created['name']
        assert data['contact'] == client_created['contact']

        client = Client.objects.get(id=client_id)
        assert client.phone == '13900139002'
        assert client.name == client_created['name']

    # ========== TC-API-047 客户删除接口验证 ==========
    def test_delete_client(self, api_client, client_created):
        client_id = client_created['id']
        url = f'/api/clients/{client_id}/'
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        with pytest.raises(Client.DoesNotExist):
            Client.objects.get(id=client_id)

    # ========== TC-API-048 客户创建-联系人为空校验 ==========
    def test_create_client_missing_contact(self, api_client):
        url = '/api/clients/'
        data = {
            'number': 'C002',
            'name': '测试客户2',
            'level': '0',
            # 不传 contact 字段
            'phone': '13800138002',
        }
        response = api_client.post(url, data, format='json')
        # 系统允许 contact 为空，预期 201
        assert response.status_code == status.HTTP_201_CREATED
        client = Client.objects.get(number='C002')
        assert client.contact is None


    # ========== TC-API-049 客户删除-存在关联销售单时禁止删除 ==========
    def test_delete_client_referenced_by_sales(
        self, api_client, admin_user, product_a, warehouse_active
    ):
        # ----- 1. 创建一个客户 -----
        client = Client.objects.create(
            number='C999',
            name='测试客户-删除测试',
            level='1',
            contact='张经理',
            phone='13800138001',
            email='test@example.com',
            address='测试地址',
            is_active=True,
            team=admin_user.team,
        )
        client_id = client.id
        client_number = client.number

        # ----- 2. 创建销售单并完成出库（引用该客户） -----
        # 2.1 创建销售单
        sales_order = SalesOrder.objects.create(
            number='XS-REF-CLIENT-001',
            warehouse=warehouse_active,
            client=client,
            handler=admin_user,
            handle_time=timezone.now().date(),
            total_quantity=20.0,
            total_amount=3000.0,
            arrears_amount=3000.0,
            creator=admin_user,
            team=admin_user.team,
        )
        # 2.2 创建销售明细
        SalesGoods.objects.create(
            sales_order=sales_order,
            goods=product_a,
            sales_quantity=20.0,
            sales_price=150.0,
            total_amount=3000.0,
            team=admin_user.team,
        )
        # 2.3 创建出库通知单（已完成）
        stock_out_order = StockOutOrder.objects.create(
            number='CK-REF-CLIENT-001',
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
        # 2.4 创建出库记录（模拟已执行出库）
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

        # ----- 3. 尝试删除被引用的客户 -----
        delete_url = f'/api/clients/{client_id}/'
        response = api_client.delete(delete_url)

        # 断言状态码 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST, \
            f"期望400，实际{response.status_code}"

        # 断言错误信息包含“被引用”或客户被销售单引用相关提示
        error_msg = str(response.data)
        expected_keywords = ['引用', '销售单', 'XS-REF-CLIENT-001', '客户已被引用']
        assert any(keyword in error_msg for keyword in expected_keywords), \
            f"错误信息未包含预期内容，实际返回：{error_msg}"

        # ----- 4. 验证客户未被删除 -----
        client_exists = Client.objects.filter(id=client_id).exists()
        assert client_exists is True, "客户记录已被删除，但预期应保留"

        # 额外检查：客户仍为启用状态
        client.refresh_from_db()
        assert client.is_active is True, "客户被误设为非激活状态"