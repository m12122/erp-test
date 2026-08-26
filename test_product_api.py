import pytest
from django.urls import reverse
from rest_framework import status
from apps.goods.models import Goods, GoodsCategory


@pytest.fixture
def goods_category(db, admin_user):
    # 创建产品分类
    return GoodsCategory.objects.create(
        name='测试分类',
        remark='测试用',
        team=admin_user.team,
    )


@pytest.fixture
def product_data(goods_category, admin_user):
    # 创建有效产品
    return {
        'number': 'P999',
        'name': '测试产品',
        'category': goods_category.id,          # 外键传 ID
        'unit': None,                           # 单位可为空
        'spec': '规格',
        'purchase_price': 100.0,
        'retail_price': 150.0,
    }


@pytest.fixture
def created_product(api_client, product_data):
    # 创建一个产品供后续测试使用
    url = '/api/goods/'                         
    response = api_client.post(url, product_data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


@pytest.mark.django_db
class TestProductAPI:

    # ========== TC-API-001 产品创建成功 ==========
    def test_create_product_success(self, api_client, product_data):
        url = '/api/goods/'
        response = api_client.post(url, product_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data
        assert data['name'] == product_data['name']
        assert data['number'] == product_data['number']
        assert data['purchase_price'] == product_data['purchase_price']

        # 数据库验证
        goods = Goods.objects.get(number=product_data['number'])
        assert goods.name == product_data['name']

    # ========== TC-API-002 产品列表查询 ==========
    def test_list_products(self, api_client, created_product):
        # 使用默认分页（不带参数也行，但为了测试 page 参数）
        url = '/api/goods/?page=1'
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        # DRF 默认分页返回格式：{"count": X, "next": "...", "previous": "...", "results": [...]}
        assert 'results' in data
        assert len(data['results']) >= 1
        item = data['results'][0]
        # 验证必要字段存在
        assert 'id' in item
        assert 'name' in item
        assert 'number' in item

    # ========== TC-API-003 产品更新（部分字段） ==========
    def test_update_product_partial(self, api_client, created_product):
        product_id = created_product['id']
        url = f'/api/goods/{product_id}/'
        update_data = {'retail_price': 200.0}
        response = api_client.patch(url, update_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data['retail_price'] == 200.0
        # 验证其他字段不变
        assert data['name'] == created_product['name']
        assert data['purchase_price'] == created_product['purchase_price']

        goods = Goods.objects.get(id=product_id)
        assert goods.retail_price == 200.0
        assert goods.name == created_product['name']

    # ========== TC-API-004 产品删除（硬删除） ==========
    # 项目 GoodsViewSet 使用 ModelViewSet，destroy 为硬删除（物理删除）
    def test_delete_product(self, api_client, created_product):
        product_id = created_product['id']
        url = f'/api/goods/{product_id}/'
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # 验证数据库中记录已被删除
        with pytest.raises(Goods.DoesNotExist):
            Goods.objects.get(id=product_id)

    # ========== TC-API-005 创建-缺少必填项（name） ==========
    def test_create_product_missing_name(self, api_client, goods_category):
        url = '/api/goods/'
        data = {
            'number': 'P998',
            'category': goods_category.id,
            'purchase_price': 100.0,
            # 缺少 name
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # DRF 标准错误格式：{"name": ["This field is required."]}
        assert 'name' in response.data
        assert 'required' in str(response.data['name']).lower()

    # ========== TC-API-006 创建-超长名称（>64） ==========
    def test_create_product_name_too_long(self, api_client, goods_category):
        url = '/api/goods/'
        long_name = 'a' * 65   # 超过模型 max_length=64
        data = {
            'number': 'P997',
            'name': long_name,
            'category': goods_category.id,
            'purchase_price': 100.0,
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # DRF 错误格式通常包含字段名 'name'
        assert 'name' in response.data
        # 错误信息可能包含 "max_length" 或 "长度"
        error_msg = str(response.data['name']).lower()
        assert '64 characters' in error_msg or 'max_length' in error_msg


    # ========== TC-API-007 创建-负数价格 ==========
    def test_create_product_negative_price(self, api_client, goods_category):
        url = '/api/goods/'
        data = {
            'number': 'P996',
            'name': '测试负数价格',
            'category': goods_category.id,
            'purchase_price': -100.0,
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        # 验证数据库中的价格确实为 -100.0
        goods = Goods.objects.get(number='P996')
        assert goods.purchase_price == -100.0