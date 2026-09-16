import pytest
from django.utils import timezone
from rest_framework import status
from decimal import Decimal

from apps.data.models import Account, Supplier, Client
from apps.finance.models import PaymentOrder, CollectionOrder, AccountTransferRecord
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder

from decimal import Decimal
from django.db.models import Sum
from unittest import mock
from apps.stock_out.models import StockOutOrder, StockOutGoods

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
def supplier_active(db, admin_user):
    # 创建启用状态的供应商
    return Supplier.objects.create(
        number='S001',
        name='测试供应商',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def account_wechat(db, admin_user):
    # 微信账户，余额10000
    return Account.objects.create(
        number='A002',
        name='微信账户',
        type=Account.Type.WECHAT,
        is_active=True,
        balance_amount=10000.0,
        has_balance=True,
        team=admin_user.team,
    )


@pytest.fixture
def account_bank(db, admin_user):
    # 银行账户，余额5000
    return Account.objects.create(
        number='A003',
        name='银行账户',
        type=Account.Type.BANK_ACCOUNT,
        is_active=True,
        balance_amount=5000.0,
        has_balance=True,
        team=admin_user.team,
    )


@pytest.fixture
def account_low_balance(db, admin_user):
    # 余额1000的账户
    return Account.objects.create(
        number='A004',
        name='低余额账户',
        type=Account.Type.CASH,
        is_active=True,
        balance_amount=1000.0,
        has_balance=True,
        team=admin_user.team,
    )


# ==================== Test Class ====================

@pytest.mark.django_db
class TestFinanceManagement:

    # ========== TC-API-027 付款接口-正常付款验证 ==========
    def test_payment_success(self, api_client, admin_user, supplier_active, account_wechat):
        # 正常付款：账户余额10000，付款5000，余额变为5000
        url = '/api/payment_orders/'
        data = {
            'number': 'FK202608160001',
            'supplier': supplier_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'payment_account_items': [
                {
                    'account': account_wechat.id,
                    'payment_amount': 5000.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        payment_order = PaymentOrder.objects.get(number='FK202608160001')
        assert payment_order.total_amount == 5000.0

        # 验证账户余额减少
        account_wechat.refresh_from_db()
        assert account_wechat.balance_amount == 5000.0

        # 验证付款记录存在
        assert PaymentOrder.objects.filter(number='FK202608160001').exists()

    # ========== TC-API-028 付款-余额不足异常校验 ==========
    def test_payment_insufficient_balance(self, api_client, admin_user, supplier_active, account_low_balance):
        # 余额1000，付款8000，报错
        url = '/api/payment_orders/'
        data = {
            'number': 'FK202608160002',
            'supplier': supplier_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'payment_account_items': [
                {
                    'account': account_low_balance.id,
                    'payment_amount': 8000.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        # 余额不足抛出 ValidationError，返回400
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = str(response.data).lower()
        assert '余额不足' in error_msg or 'insufficient' in error_msg

    # ========== TC-API-029 收款接口-正常收款验证 ==========
    def test_collection_success(self, api_client, admin_user, client_active, account_wechat):
        # 正常收款：账户余额10000，收款3000，余额变为13000
        url = '/api/collection_orders/'
        data = {
            'number': 'SK202608160001',
            'client': client_active.id,
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'collection_account_items': [
                {
                    'account': account_wechat.id,
                    'collection_amount': 3000.0,
                }
            ]
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        collection_order = CollectionOrder.objects.get(number='SK202608160001')
        assert collection_order.total_amount == 3000.0

        # 验证账户余额增加（10000 + 3000 = 13000）
        account_wechat.refresh_from_db()
        assert account_wechat.balance_amount == 13000.0

        # 验证收款记录存在
        assert CollectionOrder.objects.filter(number='SK202608160001').exists()

    # ========== TC-API-030 账户转账-金额超出余额校验 ==========
    def test_transfer_exceeds_balance(self, api_client, admin_user, account_wechat, account_bank):
        # 转账20000，微信余额10000，报错
        url = '/api/account_transfer_records/'
        data = {
            'out_account': account_wechat.id,
            'in_account': account_bank.id,
            'transfer_amount': 20000.0,
            'transfer_out_time': timezone.now(),
            'transfer_in_time': timezone.now(),
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
        }
        response = api_client.post(url, data, format='json')
        # perform_create 中会校验余额不足
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = str(response.data).lower()
        assert '余额不足' in error_msg or 'insufficient' in error_msg

        # 验证余额未变
        account_wechat.refresh_from_db()
        account_bank.refresh_from_db()
        assert account_wechat.balance_amount == 10000.0
        assert account_bank.balance_amount == 5000.0

        # 转账记录不应新增（事务回滚）
        transfer_records = AccountTransferRecord.objects.filter(out_account=account_wechat, in_account=account_bank)
        assert transfer_records.count() == 0

    # ========== TC-API-031 账户转账-金额为0校验 ==========
    def test_transfer_zero_amount(self, api_client, admin_user, account_wechat, account_bank):
        # 转账金额为0，系统允许（无业务校验），余额不变
        url = '/api/account_transfer_records/'
        data = {
            'out_account': account_wechat.id,
            'in_account': account_bank.id,
            'transfer_amount': 0.0,
            'transfer_out_time': timezone.now(),
            'transfer_in_time': timezone.now(),
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
        }
        response = api_client.post(url, data, format='json')
        # 系统未对金额做大于0校验，返回201
        assert response.status_code == status.HTTP_201_CREATED

        # 验证余额未变
        account_wechat.refresh_from_db()
        account_bank.refresh_from_db()
        assert account_wechat.balance_amount == 10000.0
        assert account_bank.balance_amount == 5000.0