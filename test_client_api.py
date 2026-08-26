import pytest
from django.utils import timezone
from rest_framework import status

from apps.data.models import Client


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

    # ========== TC-API-039 客户创建接口验证 ==========
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

    # ========== TC-API-040 客户列表查询接口验证 ==========
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

    # ========== TC-API-041 客户更新接口验证（修改电话） ==========
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

    # ========== TC-API-042 客户删除接口验证 ==========
    def test_delete_client(self, api_client, client_created):
        client_id = client_created['id']
        url = f'/api/clients/{client_id}/'
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        with pytest.raises(Client.DoesNotExist):
            Client.objects.get(id=client_id)

    # ========== TC-API-043 客户创建-联系人为空校验 ==========
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