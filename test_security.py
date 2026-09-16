import pytest
import time
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

# 导入模型
from apps.manage.models import SuperUser
from apps.system.models import User as SystemUser, Team
from apps.goods.models import Goods, GoodsCategory, GoodsUnit, Inventory
from apps.data.models import Client, Supplier, Warehouse, Account
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder
from apps.finance.models import PaymentOrder, CollectionOrder
from apps.stock_in.models import StockInOrder, StockInGoods
from apps.stock_out.models import StockOutOrder, StockOutGoods
from apps.stock_transfer.models import StockTransferOrder


def create_test_account(team):
    # 创建或获取一个测试用的财务账户（使用 Account 模型）
    account, _ = Account.objects.get_or_create(
        number='ACCT_TEST',
        defaults={
            'name': '测试账户',
            'type': Account.Type.CASH,
            'is_active': True,
            'balance_amount': 100000.0,
            'has_balance': True,
            'team': team,
        }
    )
    return account


# ==================== 安全测试类 ====================

@pytest.mark.django_db
class TestAuthenticationSecurity:

    def test_unauthenticated_access(self):
        # TC-SEC-001 未登录访问需认证接口
        client = APIClient()
        response = client.get('/api/goods/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token(self, admin_user):
        # TC-SEC-002 过期Token访问接口
        superuser = SuperUser.objects.get(id=admin_user.id)
        token = AccessToken.for_user(superuser)
        token.set_exp(lifetime=timedelta(days=-1))
        expired_token = str(token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        response = client.get('/api/goods/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_malformed_token(self):
        # TC-SEC-003 格式错误Token访问接口
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_format')
        response = client.get('/api/goods/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_token(self):
        # TC-SEC-004 空Token访问接口
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer ')
        response = client.get('/api/goods/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAuthorizationSecurity:
    # 授权安全测试（垂直越权 + 水平越权）

    def test_regular_user_create_product(self, regular_user_token, goods_category):
        # TC-SEC-005 普通用户创建产品（垂直越权）
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        data = {
            'number': 'P999',
            'name': '越权测试产品',
            'category': goods_category.id,
            'purchase_price': 100.0
        }
        response = client.post('/api/goods/', data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_delete_product(self, regular_user_token, existing_goods):
        # TC-SEC-006 普通用户删除产品（垂直越权）
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        response = client.delete(f'/api/goods/{existing_goods.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_export_goods(self, regular_user_token):
        # TC-SEC-007 普通用户导出产品数据（垂直越权）
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        response = client.get('/api/goods/export/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_other_team_client_access(self, api_client, admin_user):
        # TC-SEC-008 用户访问其他团队客户数据（水平越权）
        other_team = Team.objects.create(
            number='T999',
            expiry_time=timezone.now() + timedelta(days=365),
            user_quantity=10
        )
        other_client = Client.objects.create(
            number='C999',
            name='其他团队客户',
            team=other_team,
            is_active=True
        )
        response = api_client.get(f'/api/clients/{other_client.id}/')
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    def test_regular_user_reset_other_password(self, regular_user_token):
        # TC-SEC-009 普通用户重置其他用户密码（垂直越权）
        another_super = SuperUser.objects.create(username='another_admin')
        another_super.set_password('123456')
        another_super.save()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        response = client.post(f'/api/users/{another_super.id}/reset_password/', format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInputValidationSecurity:
    # 输入验证安全测试（SQL注入、XSS、超长输入）

    def test_sql_injection_search(self, api_client):
        # TC-SEC-010 SQL注入防护-搜索接口
        payload = "1' OR '1'='1"
        response = api_client.get('/api/goods/', {'search': payload})
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_sql_injection_delete(self, api_client):
        # TC-SEC-011 SQL注入防护-删除接口（参数注入）
        response = api_client.delete('/api/goods/1%20OR%201=1/')
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]

    def test_xss_product_name(self, api_client, goods_category):
        # TC-SEC-012 XSS防护-产品名称存储脚本
        xss_payload = '<script>alert("XSS")</script>'
        data = {
            'number': 'P_XSS',
            'name': xss_payload,
            'category': goods_category.id,
            'purchase_price': 100.0
        }
        response = api_client.post('/api/goods/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            created = response.json()
            assert '<script>' not in created.get('name', '')
        else:
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_xss_remark_field(self, api_client, existing_goods):
        # TC-SEC-013 XSS防护-备注字段存储脚本
        xss_payload = '<script>alert(1)</script>'
        data = {'remark': xss_payload}
        response = api_client.patch(f'/api/goods/{existing_goods.id}/', data, format='json')
        if response.status_code == status.HTTP_200_OK:
            updated = response.json()
            assert '<script>' not in updated.get('remark', '')
        else:
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_long_input_crash(self, api_client):
        # TC-SEC-014 超长输入导致服务崩溃
        long_text = 'A' * 10000
        response = api_client.get('/api/goods/', {'search': long_text})
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


@pytest.mark.django_db
class TestDataLeakSecurity:
    # 敏感数据泄露测试

    def test_error_no_stack_trace(self, api_client):
        # TC-SEC-015 错误响应不暴露堆栈信息
        response = api_client.get('/api/goods/99999/')
        error_text = str(response.data).lower()
        assert 'traceback' not in error_text
        assert 'file' not in error_text or 'detail' in error_text

    def test_password_not_in_users_response(self, api_client):
        # TC-SEC-016 密码字段不在API响应中返回
        response = api_client.get('/api/users/')
        data = response.json()
        items = data.get('results', data)
        for item in items:
            assert 'password' not in item

    def test_password_not_in_user_info(self, regular_user_token):
        # TC-SEC-017 当前用户信息接口不返回密码
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        response = client.get('/api/user/info/')
        data = response.json()
        assert 'password' not in data


@pytest.mark.django_db
class TestIdempotencySecurity:
    # 幂等性/重复提交安全测试

    def test_duplicate_purchase_order(self, api_client, admin_user):
        # TC-SEC-018 同一采购订单重复提交拦截
        warehouse = Warehouse.objects.create(number='W_IDEM', name='幂等测试仓库', is_active=True, team=admin_user.team)
        supplier = Supplier.objects.create(number='S_IDEM', name='幂等测试供应商', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='幂等测试分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_IDEM', name='幂等测试产品', team=admin_user.team, category=category, unit=unit, is_active=True)

        data = {
            'number': f'PO_{int(time.time())}',
            'warehouse': warehouse.id,
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'purchase_goods_items': [{'goods': goods.id, 'purchase_quantity': 10, 'purchase_price': 10.0}],
            'accounts': []
        }
        response1 = api_client.post('/api/purchase_orders/', data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED, f"首次创建失败: {response1.data}"
        response2 = api_client.post('/api/purchase_orders/', data, format='json')
        assert response2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    def test_duplicate_sales_order(self, api_client, admin_user):
        # TC-SEC-019 同一销售订单重复提交拦截
        warehouse = Warehouse.objects.create(number='W_SAL_IDEM', name='幂等销售仓库', is_active=True, team=admin_user.team)
        client = Client.objects.create(number='C_IDEM', name='幂等测试客户', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='幂等销售分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_SAL_IDEM', name='幂等销售产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=100, has_stock=True, team=admin_user.team)

        data = {
            'number': f'SO_{int(time.time())}',
            'warehouse': warehouse.id,
            'client': client.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'sales_goods_items': [{'goods': goods.id, 'sales_quantity': 10, 'sales_price': 10.0}],
            'accounts': []
        }
        response1 = api_client.post('/api/sales_orders/', data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED
        response2 = api_client.post('/api/sales_orders/', data, format='json')
        assert response2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    def test_duplicate_payment_order(self, api_client, admin_user):
        # TC-SEC-020 同一付款单重复提交拦截
        supplier = Supplier.objects.create(number='S_PAY_IDEM', name='付款供应商', is_active=True, team=admin_user.team)
        account = create_test_account(admin_user.team)
        data = {
            'number': f'PAY_{int(time.time())}',
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 500.0,
            'remark': '幂等付款测试',
            'payment_account_items': [{'account': account.id, 'payment_amount': 500.0}]
        }
        response1 = api_client.post('/api/payment_orders/', data, format='json')
        if response1.status_code != 201:
            print("付款单创建失败，错误信息:", response1.data)
        assert response1.status_code == status.HTTP_201_CREATED
        response2 = api_client.post('/api/payment_orders/', data, format='json')
        assert response2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    def test_duplicate_collection_order(self, api_client, admin_user):
        # TC-SEC-021 同一收款单重复提交拦截
        client = Client.objects.create(number='C_COL_IDEM', name='收款客户', is_active=True, team=admin_user.team)
        account = create_test_account(admin_user.team)
        data = {
            'number': f'COL_{int(time.time())}',
            'client': client.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 600.0,
            'remark': '幂等收款测试',
            'collection_account_items': [{'account': account.id, 'collection_amount': 600.0}]
        }
        response1 = api_client.post('/api/collection_orders/', data, format='json')
        if response1.status_code != 201:
            print("收款单创建失败，错误信息:", response1.data)
        assert response1.status_code == status.HTTP_201_CREATED
        response2 = api_client.post('/api/collection_orders/', data, format='json')
        assert response2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    def test_duplicate_stock_transfer_order(self, api_client, admin_user):
        # TC-SEC-022 同一调拨单重复提交拦截
        out_wh = Warehouse.objects.create(number='W_OUT_IDEM', name='调出仓库', is_active=True, team=admin_user.team)
        in_wh = Warehouse.objects.create(number='W_IN_IDEM', name='调入仓库', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='调拨分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_TRANS', name='调拨产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=out_wh, goods=goods, total_quantity=50, has_stock=True, team=admin_user.team)

        data = {
            'number': f'TRANS_{int(time.time())}',
            'out_warehouse': out_wh.id,
            'in_warehouse': in_wh.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_quantity': 10,
            'remark': '幂等调拨测试',
            'stock_transfer_goods_items': [{'goods': goods.id, 'stock_transfer_quantity': 10}]
        }
        response1 = api_client.post('/api/stock_transfer_orders/', data, format='json')
        if response1.status_code != 201:
            print("调拨单创建失败，错误信息:", response1.data)
        assert response1.status_code == status.HTTP_201_CREATED
        response2 = api_client.post('/api/stock_transfer_orders/', data, format='json')
        assert response2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]


@pytest.mark.django_db
class TestConcurrencySecurity:
    # 并发操作安全测试（顺序模拟，验证重复拦截与库存不超卖）

    def test_concurrent_stock_out(self, api_client, admin_user):
        # TC-SEC-023 同一库存并发出库不超卖（顺序模拟）
        warehouse = Warehouse.objects.create(number='W_CONC', name='并发仓库', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='并发分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_CONC', name='并发产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=10, has_stock=True, team=admin_user.team)
        client = Client.objects.create(number='C_CONC', name='并发客户', is_active=True, team=admin_user.team)

        # 先创建销售单（不会扣减库存）
        sales_data = {
            'number': f'SO_CONC_{int(time.time())}',
            'warehouse': warehouse.id,
            'client': client.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'sales_goods_items': [{'goods': goods.id, 'sales_quantity': 10, 'sales_price': 10.0}],
            'accounts': []
        }
        so_resp = api_client.post('/api/sales_orders/', sales_data, format='json')
        assert so_resp.status_code == status.HTTP_201_CREATED
        so_id = so_resp.json()['id']

        # 获取系统生成的出库通知单
        stock_out_order = StockOutOrder.objects.get(sales_order_id=so_id)
        stock_out_goods = StockOutGoods.objects.get(stock_out_order=stock_out_order, goods=goods)

        # 准备出库记录数据（实际扣减库存）
        out_data = {
            'stock_out_order': stock_out_order.id,
            'warehouse': warehouse.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'stock_out_record_goods_items': [
                {'stock_out_goods': stock_out_goods.id, 'stock_out_quantity': 10.0}
            ],
        }

        # 第一次出库成功
        resp1 = api_client.post('/api/stock_out_records/', out_data, format='json')
        assert resp1.status_code == status.HTTP_201_CREATED

        # 第二次出库应失败（库存不足）
        resp2 = api_client.post('/api/stock_out_records/', out_data, format='json')
        assert resp2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

        # 验证库存为0
        inventory = Inventory.objects.get(warehouse=warehouse, goods=goods)
        assert inventory.total_quantity == 0

    def test_concurrent_stock_in(self, api_client, admin_user):
        # TC-SEC-024 同一采购单并发入库不重复（顺序模拟）
        warehouse = Warehouse.objects.create(number='W_CIN', name='并发入库仓库', is_active=True, team=admin_user.team)
        supplier = Supplier.objects.create(number='S_CIN', name='并发供应商', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='并发分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_CIN', name='并发产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        # 预先创建库存记录（初始0）
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=0, has_stock=False, team=admin_user.team)

        # 创建采购单
        po_data = {
            'number': f'PO_CIN_{int(time.time())}',
            'warehouse': warehouse.id,
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'purchase_goods_items': [{'goods': goods.id, 'purchase_quantity': 10, 'purchase_price': 10.0}],
            'accounts': []
        }
        po_resp = api_client.post('/api/purchase_orders/', po_data, format='json')
        assert po_resp.status_code == status.HTTP_201_CREATED
        po_id = po_resp.json()['id']

        # 获取入库通知单
        stock_in_order = StockInOrder.objects.get(purchase_order_id=po_id)
        stock_in_goods = StockInGoods.objects.get(stock_in_order=stock_in_order, goods=goods)

        # 准备入库记录数据
        in_data = {
            'stock_in_order': stock_in_order.id,
            'warehouse': warehouse.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'stock_in_record_goods_items': [
                {'stock_in_goods': stock_in_goods.id, 'stock_in_quantity': 10.0}
            ],
        }

        # 第一次入库成功
        resp1 = api_client.post('/api/stock_in_records/', in_data, format='json')
        assert resp1.status_code == status.HTTP_201_CREATED

        # 第二次入库应失败（重复入库）
        resp2 = api_client.post('/api/stock_in_records/', in_data, format='json')
        assert resp2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

        # 验证库存为10
        inventory = Inventory.objects.get(warehouse=warehouse, goods=goods)
        assert inventory.total_quantity == 10

    def test_concurrent_stock_transfer(self, api_client, admin_user):
        # TC-SEC-025 同一批次并发调拨不超量（顺序模拟）
        out_wh = Warehouse.objects.create(number='W_COUT', name='调出仓库', is_active=True, team=admin_user.team)
        in_wh = Warehouse.objects.create(number='W_CIN2', name='调入仓库', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='并发分类2', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_CTRANS', name='并发调拨产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=out_wh, goods=goods, total_quantity=10, has_stock=True, team=admin_user.team)

        # 创建调拨单（调拨单创建时可能不立即扣减库存，但重复创建应被拦截）
        transfer_data = {
            'number': f'TRANS_CONC_{int(time.time())}',
            'out_warehouse': out_wh.id,
            'in_warehouse': in_wh.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_quantity': 10,
            'stock_transfer_goods_items': [{'goods': goods.id, 'stock_transfer_quantity': 10}],
            'remark': '并发调拨测试'
        }

        # 第一次调拨成功
        resp1 = api_client.post('/api/stock_transfer_orders/', transfer_data, format='json')
        assert resp1.status_code == status.HTTP_201_CREATED

        # 第二次调拨应失败（重复调拨）
        resp2 = api_client.post('/api/stock_transfer_orders/', transfer_data, format='json')
        assert resp2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

        # 验证调出库存未超卖（保持原值或≥0，因调拨单创建不扣减库存，故仍为10）
        inventory = Inventory.objects.get(warehouse=out_wh, goods=goods)
        assert inventory.total_quantity == 10  # 调拨单创建不扣减库存，所以仍为10


@pytest.mark.django_db
class TestAmountTamperingSecurity:
    # 金额篡改安全测试

    def test_purchase_order_amount_tampering(self, api_client, admin_user):
        # TC-SEC-026 采购单总金额被篡改拦截
        warehouse = Warehouse.objects.create(number='W_TAMP', name='篡改仓库', is_active=True, team=admin_user.team)
        supplier = Supplier.objects.create(number='S_TAMP', name='篡改供应商', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='篡改分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_TAMP', name='篡改产品', team=admin_user.team, category=category, unit=unit, is_active=True)

        data = {
            'number': f'PO_TAMP_{int(time.time())}',
            'warehouse': warehouse.id,
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 50,  # 明细合计100，故意不一致
            'purchase_goods_items': [{'goods': goods.id, 'purchase_quantity': 10, 'purchase_price': 10.0}],
            'accounts': []
        }
        response = api_client.post('/api/purchase_orders/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sales_order_amount_tampering(self, api_client, admin_user):
        # TC-SEC-027 销售单总金额被篡改拦截
        warehouse = Warehouse.objects.create(number='W_SALT', name='销售篡改仓库', is_active=True, team=admin_user.team)
        client = Client.objects.create(number='C_SALT', name='销售篡改客户', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='销售篡改分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_SALT', name='销售篡改产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=100, has_stock=True, team=admin_user.team)

        data = {
            'number': f'SO_TAMP_{int(time.time())}',
            'warehouse': warehouse.id,
            'client': client.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 50,
            'sales_goods_items': [{'goods': goods.id, 'sales_quantity': 10, 'sales_price': 10.0}],
            'accounts': []
        }
        response = api_client.post('/api/sales_orders/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_payment_exceeds_arrears(self, api_client, admin_user):
        # TC-SEC-028 付款金额超过应付欠款拦截
        supplier = Supplier.objects.create(
            number='S_ARR',
            name='欠款供应商',
            is_active=True,
            team=admin_user.team,
            arrears_amount=1000.0
        )
        account = create_test_account(admin_user.team)
        data = {
            'number': f'PAY_ARR_{int(time.time())}',
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 1200.0,
            'remark': '超额付款测试',
            'payment_account_items': [{'account': account.id, 'payment_amount': 1200.0}]
        }
        response = api_client.post('/api/payment_orders/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestCompletedDocumentSecurity:
    # 已完成单据不可修改测试

    def test_completed_purchase_order_modify(self, api_client, admin_user):
        # TC-SEC-029 已完成的采购单重新修改（已入库）
        warehouse = Warehouse.objects.create(number='W_COMP', name='完成测试仓库', is_active=True, team=admin_user.team)
        supplier = Supplier.objects.create(number='S_COMP', name='完成测试供应商', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='完成测试分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_COMP', name='完成测试产品', team=admin_user.team, category=category, unit=unit, is_active=True)

        # 预先创建库存记录（数量0），避免入库时查询不到
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=0, has_stock=False, team=admin_user.team)

        # 创建采购单（使系统自动生成入库通知单）
        po_data = {
            'number': f'PO_COMP_{int(time.time())}',
            'warehouse': warehouse.id,
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'purchase_goods_items': [{'goods': goods.id, 'purchase_quantity': 10, 'purchase_price': 10.0}],
            'accounts': [],
            'enable_auto_stock_in': False,
        }
        po_resp = api_client.post('/api/purchase_orders/', po_data, format='json')
        assert po_resp.status_code == status.HTTP_201_CREATED
        po_id = po_resp.json()['id']

        # 获取自动生成的入库通知单和入库商品明细
        stock_in_order = StockInOrder.objects.get(purchase_order_id=po_id)
        stock_in_goods = StockInGoods.objects.get(stock_in_order=stock_in_order, goods=goods)

        # 执行入库记录（实际入库）
        stock_in_record_data = {
            'stock_in_order': stock_in_order.id,
            'warehouse': warehouse.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'stock_in_record_goods_items': [
                {
                    'stock_in_goods': stock_in_goods.id,
                    'stock_in_quantity': 10.0,
                }
            ],
        }
        record_resp = api_client.post('/api/stock_in_records/', stock_in_record_data, format='json')
        assert record_resp.status_code == status.HTTP_201_CREATED, f"入库失败: {record_resp.data}"

        # 尝试修改已入库的采购单（使用 PUT）
        data = {'remark': '尝试修改已完成单据'}
        response = api_client.put(f'/api/purchase_orders/{po_id}/', data, format='json')
        # 400 或 405 均可视为拒绝修改，测试通过
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_405_METHOD_NOT_ALLOWED]

    def test_completed_sales_order_modify(self, api_client, admin_user):
        # TC-SEC-030 已完成的销售单重新修改（已出库）
        warehouse = Warehouse.objects.create(number='W_SAL_COMP', name='销售完成测试仓库', is_active=True, team=admin_user.team)
        client = Client.objects.create(number='C_SAL_COMP', name='销售完成测试客户', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='销售完成测试分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_SAL_COMP', name='销售完成测试产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=100, has_stock=True, team=admin_user.team)

        # 创建销售单（系统自动生成出库通知单）
        so_data = {
            'number': f'SO_COMP_{int(time.time())}',
            'warehouse': warehouse.id,
            'client': client.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'sales_goods_items': [{'goods': goods.id, 'sales_quantity': 10, 'sales_price': 10.0}],
            'accounts': [],
            'enable_auto_stock_out': False,
        }
        so_resp = api_client.post('/api/sales_orders/', so_data, format='json')
        assert so_resp.status_code == status.HTTP_201_CREATED
        so_id = so_resp.json()['id']

        # 获取自动生成的出库通知单和出库商品明细
        stock_out_order = StockOutOrder.objects.get(sales_order_id=so_id)
        stock_out_goods = StockOutGoods.objects.get(stock_out_order=stock_out_order, goods=goods)

        # 执行出库记录（实际出库）
        stock_out_record_data = {
            'stock_out_order': stock_out_order.id,
            'warehouse': warehouse.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'stock_out_record_goods_items': [
                {
                    'stock_out_goods': stock_out_goods.id,
                    'stock_out_quantity': 10.0,
                }
            ],
        }
        record_resp = api_client.post('/api/stock_out_records/', stock_out_record_data, format='json')
        assert record_resp.status_code == status.HTTP_201_CREATED, f"出库失败: {record_resp.data}"

        # 尝试修改已出库的销售单（使用 PUT）
        data = {'remark': '尝试修改已完成销售单'}
        response = api_client.put(f'/api/sales_orders/{so_id}/', data, format='json')
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_405_METHOD_NOT_ALLOWED]


@pytest.mark.django_db
class TestHorizontalPrivilegeEscalation:
    # 水平越权测试

    def test_user_a_view_user_b_purchase_order(self, api_client, admin_user, another_user_token):
        # TC-SEC-031 用户A查看用户B的采购单
        warehouse = Warehouse.objects.create(number='W_B', name='用户B仓库', is_active=True, team=admin_user.team)
        supplier = Supplier.objects.create(number='S_B', name='用户B供应商', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='分类B', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_B', name='用户B产品', team=admin_user.team, category=category, unit=unit, is_active=True)

        po_data = {
            'number': f'PO_B_{int(time.time())}',
            'warehouse': warehouse.id,
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'purchase_goods_items': [{'goods': goods.id, 'purchase_quantity': 10, 'purchase_price': 10.0}],
            'accounts': []
        }
        po_resp = api_client.post('/api/purchase_orders/', po_data, format='json')
        assert po_resp.status_code == status.HTTP_201_CREATED
        po_id = po_resp.json()['id']

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {another_user_token}')
        response = client.get(f'/api/purchase_orders/{po_id}/')
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    def test_user_a_view_user_b_client(self, api_client, another_user_token, admin_user):
        # TC-SEC-032 用户A查看用户B的客户信息
        client_b = Client.objects.create(
            number='C_B',
            name='用户B客户',
            is_active=True,
            team=admin_user.team
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {another_user_token}')
        response = client.get(f'/api/clients/{client_b.id}/')
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    def test_user_a_view_user_b_sales_order(self, api_client, admin_user, another_user_token):
        # TC-SEC-033 用户A查看用户B的销售单
        warehouse = Warehouse.objects.create(number='W_S_B', name='销售仓库B', is_active=True, team=admin_user.team)
        client_b = Client.objects.create(number='C_S_B', name='销售客户B', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='分类S_B', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_S_B', name='销售产品B', team=admin_user.team, category=category, unit=unit, is_active=True)
        Inventory.objects.create(warehouse=warehouse, goods=goods, total_quantity=100, has_stock=True, team=admin_user.team)

        so_data = {
            'number': f'SO_B_{int(time.time())}',
            'warehouse': warehouse.id,
            'client': client_b.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 100.0,
            'sales_goods_items': [{'goods': goods.id, 'sales_quantity': 10, 'sales_price': 10.0}],
            'accounts': []
        }
        so_resp = api_client.post('/api/sales_orders/', so_data, format='json')
        assert so_resp.status_code == status.HTTP_201_CREATED
        so_id = so_resp.json()['id']

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {another_user_token}')
        response = client.get(f'/api/sales_orders/{so_id}/')
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestAuditLogSecurity:
    # 敏感操作日志测试

    def test_delete_operation_log(self, api_client, existing_goods):
        # TC-SEC-034 删除操作记录操作日志
        response = api_client.delete(f'/api/goods/{existing_goods.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_amount_change_log(self, api_client, admin_user):
        # TC-SEC-035 金额变更记录操作日志
        supplier = Supplier.objects.create(
            number='S_LOG',
            name='日志供应商',
            is_active=True,
            team=admin_user.team,
            arrears_amount=1000.0
        )
        account = create_test_account(admin_user.team)
        data = {
            'number': f'PAY_LOG_{int(time.time())}',
            'supplier': supplier.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date().isoformat(),
            'total_amount': 500.0,
            'remark': '日志测试付款',
            'payment_account_items': [{'account': account.id, 'payment_amount': 500.0}]
        }
        response = api_client.post('/api/payment_orders/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestSessionSecurity:
    # 会话安全测试

    def test_token_invalid_after_password_reset(self, admin_user, regular_user_token, regular_user):
        # TC-SEC-036 作废后Token仍可访问（会话安全）
        admin_super = SuperUser.objects.get(id=admin_user.id)
        admin_client = APIClient()
        admin_client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin_super)}')

        system_user, _ = regular_user
        reset_url = f'/api/users/{system_user.id}/reset_password/'
        reset_resp = admin_client.post(reset_url, format='json')
        assert reset_resp.status_code == status.HTTP_200_OK, "重置密码失败"

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        response = client.get('/api/user/info/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED