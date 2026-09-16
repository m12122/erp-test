import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Count, Sum, F
from rest_framework import status

# 导入所需模型
from apps.sales.models import SalesOrder
from apps.purchase.models import PurchaseOrder
from apps.stock_in.models import StockInOrder
from apps.stock_out.models import StockOutOrder
from apps.goods.models import Inventory, Batch, Goods
from apps.data.models import Client, Supplier


@pytest.mark.django_db
class TestDashboardAPI:

    DASHBOARD_URL = '/api/home_overview/'

    # ---------- 1. 接口基础可用性 ----------
    def test_dashboard_returns_200(self, api_client):
        # 数据看板-接口返回200
        response = api_client.get(self.DASHBOARD_URL)
        assert response.status_code == status.HTTP_200_OK

    # ---------- 2. 返回字段完整性 ----------
    def test_dashboard_fields_exist(self, api_client):
        # 数据看板-所有预期字段存在
        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        expected_fields = [
            'sales_count', 'sales_amount', 'purchase_count',
            'stock_in_task_count', 'stock_out_task_count',
            'inventory_warning_count', 'expiration_warning_count',
            'arrears_receivable_amount', 'arrears_payable_amount'
        ]
        for field in expected_fields:
            assert field in data, f"缺少字段：{field}"
            # 验证字段值为数字（int或float）
            assert isinstance(data.get(field), (int, float)), f"字段 {field} 不是数字"

    # ---------- 3. 今日销售数据准确性 ----------
    def test_dashboard_sales_accuracy(self, api_client, admin_user):
        # 数据看板-今日销售笔数和金额与数据库一致
        today = timezone.now().date()
        # 查询今日未作废的销售单
        actual_sales = SalesOrder.objects.filter(
            create_time__date=today,
            is_void=False,
            team=admin_user.team
        ).aggregate(count=Count('id'), amount=Sum('total_amount'))

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        expected_count = actual_sales['count'] or 0
        expected_amount = actual_sales['amount'] or 0

        assert data['sales_count'] == expected_count, \
            f"销售笔数：接口{data['sales_count']}，数据库{expected_count}"
        assert round(data['sales_amount'], 2) == round(expected_amount, 2), \
            f"销售金额：接口{data['sales_amount']}，数据库{expected_amount}"

    # ---------- 4. 今日采购数据准确性 ----------
    def test_dashboard_purchase_accuracy(self, api_client, admin_user):
        # 数据看板-今日采购笔数与数据库一致
        today = timezone.now().date()
        actual_purchase = PurchaseOrder.objects.filter(
            create_time__date=today,
            is_void=False,
            team=admin_user.team
        ).count()

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert data['purchase_count'] == actual_purchase, \
            f"采购笔数：接口{data['purchase_count']}，数据库{actual_purchase}"

    # ---------- 5. 待入库任务准确性 ----------
    def test_dashboard_pending_stock_in_accuracy(self, api_client, admin_user):
        # 数据看板-待入库任务数量与数据库一致
        actual_count = StockInOrder.objects.filter(
            is_completed=False,
            is_void=False,
            team=admin_user.team
        ).count()

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert data['stock_in_task_count'] == actual_count, \
            f"待入库：接口{data['stock_in_task_count']}，数据库{actual_count}"

    # ---------- 6. 待出库任务准确性 ----------
    def test_dashboard_pending_stock_out_accuracy(self, api_client, admin_user):
        # 数据看板-待出库任务数量与数据库一致
        actual_count = StockOutOrder.objects.filter(
            is_completed=False,
            is_void=False,
            team=admin_user.team
        ).count()

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert data['stock_out_task_count'] == actual_count, \
            f"待出库：接口{data['stock_out_task_count']}，数据库{actual_count}"

    # ---------- 7. 库存预警准确性 ----------
    def test_dashboard_inventory_warning_accuracy(self, api_client, admin_user):
        # 数据看板-库存预警数量与数据库一致（逻辑：启用预警且库存超出上下限）
        actual_count = Inventory.objects.filter(
            team=admin_user.team,
            goods__enable_inventory_warning=True,
            total_quantity__gt=F('goods__inventory_upper'),
            total_quantity__lt=F('goods__inventory_lower')
        ).count()

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert data['inventory_warning_count'] == actual_count, \
            f"库存预警：接口{data['inventory_warning_count']}，数据库{actual_count}"

    # ---------- 8. 临期预警准确性 ----------
    def test_dashboard_expiration_warning_accuracy(self, api_client, admin_user):
        # 数据看板-临期预警数量与数据库一致（逻辑：有库存且启用了批次控制且预警日期<=今天且过期日期>=今天）
        today_date = timezone.now().date().isoformat()
        actual_count = Batch.objects.filter(
            team=admin_user.team,
            has_stock=True,
            goods__enable_batch_control=True,
            goods__is_active=True,
            production_date__isnull=False,
            warning_date__lte=today_date,
            expiration_date__gte=today_date
        ).count()

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert data.get('expiration_warning_count', 0) == actual_count, \
            f"临期预警：接口{data.get('expiration_warning_count')}，数据库{actual_count}"

    # ---------- 9. 应收欠款准确性 ----------
    def test_dashboard_receivable_arrears_accuracy(self, api_client, admin_user):
        # 数据看板-应收欠款总额与数据库一致
        actual_amount = Client.objects.filter(
            is_active=True,
            has_arrears=True,
            team=admin_user.team
        ).aggregate(total=Sum('arrears_amount'))['total'] or 0

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert round(data['arrears_receivable_amount'], 2) == round(actual_amount, 2), \
            f"应收欠款：接口{data['arrears_receivable_amount']}，数据库{actual_amount}"

    # ---------- 10. 应付欠款准确性 ----------
    def test_dashboard_payable_arrears_accuracy(self, api_client, admin_user):
        # 数据看板-应付欠款总额与数据库一致
        actual_amount = Supplier.objects.filter(
            is_active=True,
            has_arrears=True,
            team=admin_user.team
        ).aggregate(total=Sum('arrears_amount'))['total'] or 0

        response = api_client.get(self.DASHBOARD_URL)
        data = response.json()

        assert round(data['arrears_payable_amount'], 2) == round(actual_amount, 2), \
            f"应付欠款：接口{data['arrears_payable_amount']}，数据库{actual_amount}"

    # ---------- 11. 非法参数容错 ----------
    def test_dashboard_invalid_parameter(self, api_client):
        # 数据看板-传入非法参数不返回500（接口会忽略参数）
        response = api_client.get(self.DASHBOARD_URL, {'invalid_field': 'value'})
        assert response.status_code == status.HTTP_200_OK
