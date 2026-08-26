import pytest
from django.utils import timezone

from apps.data.models import Account
from apps.finance.models import AccountTransferRecord


@pytest.fixture
def account_wechat(db, admin_user):
    # 微信账户，初始余额 10000
    return Account.objects.create(
        number='A002',
        name='微信账户',
        type=Account.Type.WECHAT,
        is_active=True,
        initial_balance_amount=10000.0,
        balance_amount=10000.0,
        has_balance=True,
        team=admin_user.team,
    )


@pytest.fixture
def account_bank(db, admin_user):
    # 银行账户，初始余额 5000
    return Account.objects.create(
        number='A003',
        name='银行账户',
        type=Account.Type.BANK_ACCOUNT,
        is_active=True,
        initial_balance_amount=5000.0,
        balance_amount=5000.0,
        has_balance=True,
        team=admin_user.team,
    )


@pytest.mark.django_db
class TestAccountTransfer:
    def test_account_transfer_positive_flow(
        self,
        api_client,
        admin_user,
        account_wechat,
        account_bank,
    ):
        # ========== 步骤1：发起账户转账 ==========
        transfer_data = {
            'out_account': account_wechat.id,
            'in_account': account_bank.id,
            'transfer_amount': 2000.0,
            'transfer_out_time': timezone.now(),
            'transfer_in_time': timezone.now(),
            'handler': admin_user.id,
            'handle_time': timezone.now().date(),
            'service_charge_amount': 0.0,
            'service_charge_payer': AccountTransferRecord.ServiceChargePayer.TRANSFER_OUT,
        }

        url = '/api/account_transfer_records/'
        response = api_client.post(url, transfer_data, format='json')

        assert response.status_code == 201, f"创建转账记录失败: {response.content}"

        # ========== 验证结果 ==========
        # 1. 微信账户余额变为 8000
        account_wechat.refresh_from_db()
        assert account_wechat.balance_amount == 8000.0, f"微信余额应为8000，实际{account_wechat.balance_amount}"

        # 2. 银行账户余额变为 7000
        account_bank.refresh_from_db()
        assert account_bank.balance_amount == 7000.0, f"银行余额应为7000，实际{account_bank.balance_amount}"

        # 3. 验证转账记录状态
        transfer_record = AccountTransferRecord.objects.get(
            out_account=account_wechat,
            in_account=account_bank,
        )
        assert transfer_record.is_void is False, "转账记录不应被作废"
        assert transfer_record.transfer_amount == 2000.0, f"转账金额应为2000，实际{transfer_record.transfer_amount}"