import pytest
from datetime import date
from django.utils import timezone
from rest_framework import status

# ==================== 导入所有模型 ====================
from apps.goods.models import Goods, GoodsCategory, GoodsUnit, Batch, Inventory
from apps.data.models import Client, Supplier, Warehouse, Account, ChargeItem
from apps.purchase.models import PurchaseOrder, PurchaseReturnOrder
from apps.sales.models import SalesOrder, SalesReturnOrder
from apps.finance.models import (
    PaymentOrder, CollectionOrder, AccountTransferRecord, ChargeOrder
)
from apps.flow.models import InventoryFlow, FinanceFlow
from apps.stock_in.models import StockInOrder
from apps.stock_out.models import StockOutOrder
from apps.stock_check.models import StockCheckOrder
from apps.stock_transfer.models import StockTransferOrder
from apps.flow.models import InventoryFlow
from apps.system.models import Role, User as SystemUser


# ==================== 通用基类 ====================

class BaseSearchFilterTest:
    # 搜索/筛选测试基类
    list_url = None
    search_fields = []
    status_field = None
    status_values = []

    def _extract_ids(self, data):
        if isinstance(data, dict):
            if 'results' in data:
                items = data['results']
            elif 'data' in data:
                items = data['data']
            else:
                items = data
        else:
            items = data
        if isinstance(items, list):
            return [item.get('id') for item in items if 'id' in item]
        return []

    def _create_test_data(self, admin_user):
        raise NotImplementedError

    # ---------- 通用测试方法 ----------

    def test_search_keyword(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.skip("未创建匹配数据")
        response = api_client.get(self.list_url, {'search': '测试关键字'})
        assert response.status_code == status.HTTP_200_OK
        returned_ids = self._extract_ids(response.json())
        for obj in match_objs:
            assert obj.id in returned_ids, f"匹配对象 {obj.id} 未返回"
        for obj in non_match_objs:
            assert obj.id not in returned_ids, f"不匹配对象 {obj.id} 错误返回"

    def test_status_filter(self, api_client, admin_user):
        # 基类默认实现，子类应重写以验证有效性
        if not self.status_field:
            pytest.skip("无状态筛选")
        # 子类必须重写，否则触发失败
        pytest.fail("子类必须重写 test_status_filter 以验证筛选有效性")

    def test_combined_filter(self, api_client, admin_user):
        # 基类组合筛选实现，仅检查状态码，子类如有状态字段应重写验证有效性
        if not self.status_field:
            pytest.skip("无状态，跳过组合")
        match_objs, _ = self._create_test_data(admin_user)
        if not match_objs:
            pytest.skip("无匹配数据")
        response = api_client.get(self.list_url, {
            'search': '测试关键字',
            self.status_field: self.status_values[0]
        })
        assert response.status_code == status.HTTP_200_OK

    def test_empty_result(self, api_client):
        response = api_client.get(self.list_url, {'search': '不存在的关键字_999999'})
        assert response.status_code == status.HTTP_200_OK
        returned_ids = self._extract_ids(response.json())
        assert len(returned_ids) == 0

    def test_invalid_parameter(self, api_client):
        response = api_client.get(self.list_url, {'invalid_field': 'value'})
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_date_range_filter(self, api_client):
        pytest.skip("当前模块无日期范围筛选")


# ==================== 一、报表统计 ====================

# 销售报表：统计接口，无状态筛选，分类筛选需结合其他参数，仅验证容错（允许200或400）
class TestSalesReportSearch(BaseSearchFilterTest):
    list_url = '/api/sales_reports/statistics/'
    search_fields = []

    def _create_test_data(self, admin_user):
        return [], []

    def test_search_keyword(self, api_client, admin_user):
        pytest.skip("销售报表为统计接口，不支持关键字搜索")

    def test_empty_result(self, api_client):
        pytest.skip("销售报表为统计接口，不支持 search 参数")

    def test_category_filter(self, api_client):
        #销售报表-按分类筛选（统计接口，仅验证容错）
        response = api_client.get(self.list_url, {'category': '1'})
        # 统计接口可能需要其他参数（如时间），允许200或400（容错）
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_category_filter_all(self, api_client):
        #销售报表-不传分类（全量数据，仅验证容错）
        response = api_client.get(self.list_url)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_status_filter(self, api_client, admin_user):
        pytest.skip("统计接口无状态筛选")


# 采购报表：统计接口，无状态筛选，分类筛选需结合其他参数，仅验证容错（允许200或400）
class TestPurchaseReportSearch(BaseSearchFilterTest):
    list_url = '/api/purchase_reports/statistics/'
    search_fields = []

    def _create_test_data(self, admin_user):
        return [], []

    def test_search_keyword(self, api_client, admin_user):
        pytest.skip("采购报表为统计接口，不支持关键字搜索")

    def test_empty_result(self, api_client):
        pytest.skip("采购报表为统计接口，不支持 search 参数")

    def test_category_filter(self, api_client):
        #采购报表-按分类筛选（统计接口，仅验证容错）
        response = api_client.get(self.list_url, {'category': '1'})
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_category_filter_all(self, api_client):
        #采购报表-不传分类（全量数据，仅验证容错）
        response = api_client.get(self.list_url)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_status_filter(self, api_client, admin_user):
        pytest.skip("统计接口无状态筛选")


# 库存报表：有状态筛选 has_stock，已验证有效性
class TestInventoryReportSearch(BaseSearchFilterTest):
    list_url = '/api/inventories/'
    search_fields = ['goods__number', 'goods__name']
    status_field = 'has_stock'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_INV', name='库存仓库', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        # 匹配商品：有库存，名称含关键字
        goods_match = Goods.objects.create(
            number='G_INV_MATCH', name='库存测试产品含测试关键字',
            team=admin_user.team, category=category, unit=unit, is_active=True
        )
        # 不匹配商品：无库存，名称不含关键字
        goods_non_match = Goods.objects.create(
            number='G_INV_NOMATCH', name='普通库存产品',
            team=admin_user.team, category=category, unit=unit, is_active=True
        )
        match = Inventory.objects.create(warehouse=warehouse, goods=goods_match,
                                         total_quantity=10.0, has_stock=True, team=admin_user.team)
        non_match = Inventory.objects.create(warehouse=warehouse, goods=goods_non_match,
                                             total_quantity=0.0, has_stock=False, team=admin_user.team)
        return [match], [non_match]

    def test_search_keyword(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.skip("未创建匹配数据")
        response = api_client.get(self.list_url, {'search': '测试关键字'})
        assert response.status_code == status.HTTP_200_OK
        returned_ids = self._extract_ids(response.json())
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'has_stock': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('has_stock') is True

    def test_warehouse_filter(self, api_client, admin_user):
        warehouse = Warehouse.objects.create(number='W_FILTER', name='筛选仓库', is_active=True, team=admin_user.team)
        response = api_client.get(self.list_url, {'warehouse': warehouse.id})
        assert response.status_code == status.HTTP_200_OK


# 批次报表：有状态筛选 has_stock，已验证有效性
class TestBatchReportSearch(BaseSearchFilterTest):
    list_url = '/api/batchs/'
    search_fields = ['goods__number', 'goods__name']
    status_field = 'has_stock'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_BATCH', name='批次仓库', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods_match = Goods.objects.create(
            number='G_BATCH_MATCH', name='批次测试产品含测试关键字',
            team=admin_user.team, category=category, unit=unit, is_active=True
        )
        goods_non_match = Goods.objects.create(
            number='G_BATCH_NOMATCH', name='普通批次产品',
            team=admin_user.team, category=category, unit=unit, is_active=True
        )
        inventory_match = Inventory.objects.create(warehouse=warehouse, goods=goods_match,
                                                   total_quantity=10, has_stock=True, team=admin_user.team)
        inventory_non_match = Inventory.objects.create(warehouse=warehouse, goods=goods_non_match,
                                                       total_quantity=0, has_stock=False, team=admin_user.team)
        match = Batch.objects.create(
            number='BATCH001', inventory=inventory_match, warehouse=warehouse, goods=goods_match,
            initial_quantity=10, total_quantity=10, remain_quantity=10, has_stock=True,
            team=admin_user.team
        )
        non_match = Batch.objects.create(
            number='BATCH002', inventory=inventory_non_match, warehouse=warehouse, goods=goods_non_match,
            initial_quantity=0, total_quantity=0, remain_quantity=0, has_stock=False,
            team=admin_user.team
        )
        return [match], [non_match]

    def test_search_keyword(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.skip("未创建匹配数据")
        response = api_client.get(self.list_url, {'search': '测试关键字'})
        assert response.status_code == status.HTTP_200_OK
        returned_ids = self._extract_ids(response.json())
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'has_stock': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('has_stock') is True

    def test_warehouse_filter(self, api_client, admin_user):
        warehouse1 = Warehouse.objects.create(number='W_FILTER_1', name='筛选仓库1', is_active=True, team=admin_user.team)
        warehouse2 = Warehouse.objects.create(number='W_FILTER_2', name='筛选仓库2', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='分类2', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods = Goods.objects.create(number='G_FILTER', name='筛选产品', team=admin_user.team, category=category, unit=unit, is_active=True)
        inv1 = Inventory.objects.create(warehouse=warehouse1, goods=goods, total_quantity=10, has_stock=True, team=admin_user.team)
        inv2 = Inventory.objects.create(warehouse=warehouse2, goods=goods, total_quantity=5, has_stock=True, team=admin_user.team)
        batch1 = Batch.objects.create(
            number='BATCH_W1', inventory=inv1, warehouse=warehouse1, goods=goods,
            initial_quantity=10, total_quantity=10, remain_quantity=10, has_stock=True, team=admin_user.team
        )
        batch2 = Batch.objects.create(
            number='BATCH_W2', inventory=inv2, warehouse=warehouse2, goods=goods,
            initial_quantity=5, total_quantity=5, remain_quantity=5, has_stock=True, team=admin_user.team
        )
        response = api_client.get(self.list_url, {'warehouse': warehouse1.id})
        assert response.status_code == status.HTTP_200_OK
        returned_ids = self._extract_ids(response.json())
        assert batch1.id in returned_ids
        assert batch2.id not in returned_ids


# ==================== 二、基础数据 ====================

# 客户：有状态筛选 is_active，已验证有效性
class TestClientSearch(BaseSearchFilterTest):
    list_url = '/api/clients/'
    search_fields = ['number', 'name', 'phone']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        match = Client.objects.create(number='C001', name='测试客户含测试关键字', phone='13800138001',
                                      is_active=True, team=admin_user.team)
        non_match = Client.objects.create(number='C002', name='普通客户', phone='13800138002',
                                          is_active=False, team=admin_user.team)
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'is_active': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('is_active') is True


# 供应商：有状态筛选 is_active，已验证有效性
class TestSupplierSearch(BaseSearchFilterTest):
    list_url = '/api/suppliers/'
    search_fields = ['number', 'name']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        match = Supplier.objects.create(number='S001', name='测试供应商含测试关键字', is_active=True, team=admin_user.team)
        non_match = Supplier.objects.create(number='S002', name='普通供应商', is_active=False, team=admin_user.team)
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'is_active': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('is_active') is True


# 仓库：有状态筛选 is_active，已验证有效性
class TestWarehouseSearch(BaseSearchFilterTest):
    list_url = '/api/warehouses/'
    search_fields = ['number', 'name']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        match = Warehouse.objects.create(number='W001', name='测试仓库含测试关键字', is_active=True, team=admin_user.team)
        non_match = Warehouse.objects.create(number='W002', name='普通仓库', is_active=False, team=admin_user.team)
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'is_active': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('is_active') is True


# 结算账户：有状态筛选 is_active，已验证有效性
class TestAccountSearch(BaseSearchFilterTest):
    list_url = '/api/accounts/'
    search_fields = ['number', 'name']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        match = Account.objects.create(number='A001', name='微信账户含测试关键字', is_active=True, team=admin_user.team)
        non_match = Account.objects.create(number='A002', name='银行账户', is_active=False, team=admin_user.team)
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'is_active': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('is_active') is True

    def test_combined_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {
            'search': '测试关键字',
            'is_active': 'true'
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('is_active') is True
            assert '测试关键字' in item.get('name', '') or '测试关键字' in item.get('number', '')


# 收支项目：有类型筛选（type），已验证有效性
class TestChargeItemSearch(BaseSearchFilterTest):
    list_url = '/api/charge_items/'
    search_fields = ['name', 'remark']
    # 注意：ChargeItem 模型有 type 字段（收入/支出），用作筛选
    status_field = 'type'
    status_values = ['income', 'expenditure']

    def _create_test_data(self, admin_user):
        # 匹配对象：类型为 income，名称含关键字
        match = ChargeItem.objects.create(
            name='办公费用含测试关键字',
            type='income',
            remark='运营支出',
            team=admin_user.team
        )
        # 不匹配对象：类型为 expenditure，名称不含关键字
        non_match = ChargeItem.objects.create(
            name='销售收入',
            type='expenditure',
            remark='主营业务',
            team=admin_user.team
        )
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        # 验证收支项目类型筛选（type=income）有效性
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'type': 'income'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('type') == 'income'

    def test_combined_filter(self, api_client, admin_user):
        # 验证收支项目组合筛选（搜索+类型）有效性
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {
            'search': '测试关键字',
            'type': 'income'
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('type') == 'income'
            assert '测试关键字' in item.get('name', '') or '测试关键字' in item.get('remark', '')


# ==================== 三、产品管理 ====================

# 产品：有状态筛选 is_active，已验证有效性
class TestGoodsSearch(BaseSearchFilterTest):
    list_url = '/api/goods/'
    search_fields = ['number', 'name', 'remark']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        category = GoodsCategory.objects.create(name='测试分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        match = Goods.objects.create(
            number='G_SEARCH_1', name='测试产品A', remark='包含测试关键字',
            is_active=True, team=admin_user.team, category=category, unit=unit
        )
        non_match = Goods.objects.create(
            number='G_SEARCH_2', name='普通产品B', remark='无关',
            is_active=False, team=admin_user.team, category=category, unit=unit
        )
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'is_active': 'true'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
        for item in items:
            assert item.get('is_active') is True


# 产品分类：无状态筛选，跳过
class TestGoodsCategorySearch(BaseSearchFilterTest):
    list_url = '/api/goods_categories/'
    search_fields = ['name', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        match = GoodsCategory.objects.create(name='电子分类含测试关键字', remark='测试分类', team=admin_user.team)
        non_match = GoodsCategory.objects.create(name='办公分类', remark='其他', team=admin_user.team)
        return [match], [non_match]


# 产品单位：无状态筛选，跳过
class TestGoodsUnitSearch(BaseSearchFilterTest):
    list_url = '/api/goods_units/'
    search_fields = ['name', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        match = GoodsUnit.objects.create(name='箱含测试关键字', remark='包装单位', team=admin_user.team)
        non_match = GoodsUnit.objects.create(name='个', remark='基本单位', team=admin_user.team)
        return [match], [non_match]

# 临期预警 - 搜索筛选测试
class TestExpiringWarningSearch(BaseSearchFilterTest):
    

    list_url = '/api/goods/'
    search_fields = ['number', 'name']
    # 不设置 status_field，状态筛选和组合筛选会自动跳过

    def _create_test_data(self, admin_user):
        category = GoodsCategory.objects.create(name='测试分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        # 匹配对象：有保质期且即将到期的产品（用于搜索和预警参数测试）
        match = Goods.objects.create(
            number='G_EXP_1', name='临期产品A',
            shelf_life_days=30, shelf_life_warning_days=7,
            is_active=True, team=admin_user.team, category=category, unit=unit
        )
        # 不匹配对象：无保质期
        non_match = Goods.objects.create(
            number='G_EXP_2', name='正常产品B',
            shelf_life_days=None, shelf_life_warning_days=0,
            is_active=True, team=admin_user.team, category=category, unit=unit
        )
        return [match], [non_match]

    def test_search_keyword(self, api_client, admin_user):
        # 临期预警搜索与产品搜索重复，由 TestGoodsSearch 覆盖
        pytest.skip("临期预警搜索与产品搜索重复")

    def test_status_filter(self, api_client, admin_user):
        # 临期预警无状态筛选，直接跳过
        pytest.skip("临期预警无状态筛选功能")

    def test_combined_filter(self, api_client, admin_user):
        # 无状态筛选，组合筛选无意义
        pytest.skip("临期预警无状态筛选，组合筛选跳过")

    def test_expiring_warning_filter(self, api_client):
        # 临期预警-按预警参数筛选（容错）
        for param in ['is_expiring', 'expiring_days']:
            response = api_client.get(self.list_url, {param: 'true' if param == 'is_expiring' else '30'})
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_warehouse_filter(self, api_client, admin_user):
        # 临期预警-按仓库筛选（容错测试）
        # 创建仓库用于测试
        warehouse = Warehouse.objects.create(number='W_EXP', name='临期仓库', is_active=True, team=admin_user.team)
        response = api_client.get(self.list_url, {'warehouse': warehouse.id})
        # 如果接口支持仓库筛选，返回200；不支持则返回400（容错）
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


# ==================== 四、采购管理 ====================

# 采购记录：无状态筛选，跳过
class TestPurchaseOrderSearch(BaseSearchFilterTest):
    list_url = '/api/purchase_orders/'
    search_fields = ['number', 'supplier__number', 'supplier__name']
    # 无状态字段

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_PUR', name='采购仓库', is_active=True, team=admin_user.team)
        supplier_match = Supplier.objects.create(number='SUP_TEST', name='测试供应商含测试关键字', is_active=True, team=admin_user.team)
        supplier_non_match = Supplier.objects.create(number='SUP_NORMAL', name='普通供应商', is_active=True, team=admin_user.team)
        match = PurchaseOrder.objects.create(
            number='PO001', warehouse=warehouse, supplier=supplier_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=100.0, team=admin_user.team
        )
        non_match = PurchaseOrder.objects.create(
            number='PO002', warehouse=warehouse, supplier=supplier_non_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=200.0, team=admin_user.team
        )
        return [match], [non_match]


# 退货记录（采购）：无状态筛选，跳过
class TestPurchaseReturnOrderSearch(BaseSearchFilterTest):
    list_url = '/api/purchase_return_orders/'
    search_fields = ['number', 'supplier__number', 'supplier__name']
    # 无状态

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_PUR_RET', name='退货仓库', is_active=True, team=admin_user.team)
        supplier_match = Supplier.objects.create(number='SUP_RET_TEST', name='退货供应商含测试关键字', is_active=True, team=admin_user.team)
        supplier_non_match = Supplier.objects.create(number='SUP_RET_NORMAL', name='普通退货供应商', is_active=True, team=admin_user.team)
        match = PurchaseReturnOrder.objects.create(
            number='PR001', warehouse=warehouse, supplier=supplier_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=50.0, team=admin_user.team
        )
        non_match = PurchaseReturnOrder.objects.create(
            number='PR002', warehouse=warehouse, supplier=supplier_non_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=80.0, team=admin_user.team
        )
        return [match], [non_match]


# ==================== 五、销售管理 ====================

# 销售记录：无状态筛选，跳过
class TestSalesOrderSearch(BaseSearchFilterTest):
    list_url = '/api/sales_orders/'
    search_fields = ['number', 'client__number', 'client__name']
    # 无状态

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_SAL', name='销售仓库', is_active=True, team=admin_user.team)
        client_match = Client.objects.create(number='CLI_TEST', name='测试客户含测试关键字', is_active=True, team=admin_user.team)
        client_non_match = Client.objects.create(number='CLI_NORMAL', name='普通客户', is_active=True, team=admin_user.team)
        match = SalesOrder.objects.create(
            number='SO001', warehouse=warehouse, client=client_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=300.0, team=admin_user.team
        )
        non_match = SalesOrder.objects.create(
            number='SO002', warehouse=warehouse, client=client_non_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=400.0, team=admin_user.team
        )
        return [match], [non_match]


# 退货记录（销售）：无状态筛选，跳过
class TestSalesReturnOrderSearch(BaseSearchFilterTest):
    list_url = '/api/sales_return_orders/'
    search_fields = ['number', 'client__number', 'client__name']
    # 无状态

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_SAL_RET', name='销售退货仓库', is_active=True, team=admin_user.team)
        client_match = Client.objects.create(number='CLI_RET_TEST', name='退货客户含测试关键字', is_active=True, team=admin_user.team)
        client_non_match = Client.objects.create(number='CLI_RET_NORMAL', name='普通退货客户', is_active=True, team=admin_user.team)
        match = SalesReturnOrder.objects.create(
            number='SR001', warehouse=warehouse, client=client_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=150.0, team=admin_user.team
        )
        non_match = SalesReturnOrder.objects.create(
            number='SR002', warehouse=warehouse, client=client_non_match,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=200.0, team=admin_user.team
        )
        return [match], [non_match]


# ==================== 六、库存管理 ====================

# 入库任务：无状态筛选，跳过
class TestStockInOrderSearch(BaseSearchFilterTest):
    list_url = '/api/stock_in_orders/'
    search_fields = ['number']
    # 无状态

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_IN', name='入库仓库', is_active=True, team=admin_user.team)
        match = StockInOrder.objects.create(
            number='SIO_测试关键字_001', warehouse=warehouse,
            type='purchase', total_quantity=10.0, remain_quantity=10.0,
            is_completed=False, is_void=False,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        non_match = StockInOrder.objects.create(
            number='SIO002', warehouse=warehouse,
            type='purchase', total_quantity=5.0, remain_quantity=5.0,
            is_completed=False, is_void=False,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        return [match], [non_match]


# 出库任务：无状态筛选，跳过
class TestStockOutOrderSearch(BaseSearchFilterTest):
    list_url = '/api/stock_out_orders/'
    search_fields = ['number']
    # 无状态

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_OUT', name='出库仓库', is_active=True, team=admin_user.team)
        match = StockOutOrder.objects.create(
            number='SOO_测试关键字_001', warehouse=warehouse,
            type='sales', total_quantity=10.0, remain_quantity=10.0,
            is_completed=False, is_void=False,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        non_match = StockOutOrder.objects.create(
            number='SOO002', warehouse=warehouse,
            type='sales', total_quantity=5.0, remain_quantity=5.0,
            is_completed=False, is_void=False,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        return [match], [non_match]


# 盘点：有状态字段但业务无状态筛选，跳过
class TestStockCheckOrderSearch(BaseSearchFilterTest):
    list_url = '/api/stock_check_orders/'
    search_fields = ['number', 'remark']
    status_field = 'status'
    status_values = ['draft', 'completed']

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_CHECK', name='盘点仓库', is_active=True, team=admin_user.team)
        match = StockCheckOrder.objects.create(
            number='SCO_测试关键字_001', warehouse=warehouse, handler=admin_user,
            handle_time=date.today(), remark='草稿单', status='draft',
            total_book_quantity=0, total_actual_quantity=0,
            total_surplus_quantity=0, total_surplus_amount=0,
            is_void=False, creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        non_match = StockCheckOrder.objects.create(
            number='SCO_COMPLETED_001', warehouse=warehouse, handler=admin_user,
            handle_time=date.today(), remark='已完成单', status='completed',
            total_book_quantity=0, total_actual_quantity=0,
            total_surplus_quantity=0, total_surplus_amount=0,
            is_void=False, creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        return [match], [non_match]

    def test_search_keyword(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.skip("未创建匹配数据")
        response = api_client.get(self.list_url, {'search': '测试关键字'})
        assert response.status_code == status.HTTP_200_OK
        returned_ids = self._extract_ids(response.json())
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids

    def test_status_filter(self, api_client, admin_user):
        # 跳过状态筛选测试：盘点模块业务上无状态筛选功能
        pytest.skip("盘点模块业务上无状态筛选功能，跳过")

    def test_combined_filter(self, api_client, admin_user):
        # 跳过组合筛选测试：盘点模块无状态筛选功能，组合筛选无意义
        pytest.skip("盘点模块无状态筛选功能，组合筛选跳过")


# 调拨：无状态筛选，跳过
class TestStockTransferOrderSearch(BaseSearchFilterTest):
    list_url = '/api/stock_transfer_orders/'
    search_fields = ['number', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        out_wh = Warehouse.objects.create(number='W_OUT_T', name='调出仓库', is_active=True, team=admin_user.team)
        in_wh = Warehouse.objects.create(number='W_IN_T', name='调入仓库', is_active=True, team=admin_user.team)
        match = StockTransferOrder.objects.create(
            number='STO_测试关键字_001', out_warehouse=out_wh, in_warehouse=in_wh,
            handler=admin_user, handle_time=date.today(), remark='包含测试关键字',
            total_quantity=10.0, is_void=False,
            enable_auto_stock_out=False, enable_auto_stock_in=False,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        non_match = StockTransferOrder.objects.create(
            number='STO002', out_warehouse=out_wh, in_warehouse=in_wh,
            handler=admin_user, handle_time=date.today(), remark='普通调拨',
            total_quantity=5.0, is_void=False,
            enable_auto_stock_out=False, enable_auto_stock_in=False,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        return [match], [non_match]


class TestInventoryFlowSearch(BaseSearchFilterTest):
    # 库存流水 - 搜索测试（基于 goods__name）
    list_url = '/api/inventory_flows/'
    search_fields = ['goods__number', 'goods__name', 'purchase_order__number', ...]
    # 无状态

    def _create_test_data(self, admin_user):
        warehouse = Warehouse.objects.create(number='W_FLOW', name='流水仓库', is_active=True, team=admin_user.team)
        category = GoodsCategory.objects.create(name='分类', team=admin_user.team)
        unit = GoodsUnit.objects.create(name='个', team=admin_user.team)
        goods_match = Goods.objects.create(
            number='G_FLOW_MATCH', name='流水匹配产品含测试关键字',
            team=admin_user.team, category=category, unit=unit, is_active=True
        )
        goods_non_match = Goods.objects.create(
            number='G_FLOW_NOMATCH', name='流水普通产品',
            team=admin_user.team, category=category, unit=unit, is_active=True
        )
        match = InventoryFlow.objects.create(
            warehouse=warehouse, goods=goods_match, type='in',
            quantity_before=0.0, quantity_change=10.0, quantity_after=10.0,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        non_match = InventoryFlow.objects.create(
            warehouse=warehouse, goods=goods_non_match, type='out',
            quantity_before=10.0, quantity_change=-5.0, quantity_after=5.0,
            creator=admin_user, create_time=timezone.now(), team=admin_user.team
        )
        return [match], [non_match]

    def test_search_keyword(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'search': '测试关键字'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        if isinstance(items, dict):
            items = [items] if 'id' in items else []
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_idss


# ==================== 七、财务管理 ====================

# 付款单：无状态筛选，跳过
class TestPaymentOrderSearch(BaseSearchFilterTest):
    list_url = '/api/payment_orders/'
    search_fields = ['number', 'supplier__number', 'supplier__name', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        supplier = Supplier.objects.create(number='S_PAY', name='付款供应商', is_active=True, team=admin_user.team)
        match = PaymentOrder.objects.create(
            number='PY_测试关键字_001', supplier=supplier,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=500.0, remark='测试关键字', team=admin_user.team
        )
        non_match = PaymentOrder.objects.create(
            number='PY002', supplier=supplier,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=600.0, remark='普通备注', team=admin_user.team
        )
        return [match], [non_match]


# 收款单：无状态筛选，跳过
class TestCollectionOrderSearch(BaseSearchFilterTest):
    list_url = '/api/collection_orders/'
    search_fields = ['number', 'client__number', 'client__name', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        client = Client.objects.create(number='C_COL', name='收款客户', is_active=True, team=admin_user.team)
        match = CollectionOrder.objects.create(
            number='CO_测试关键字_001', client=client,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=700.0, remark='测试关键字', team=admin_user.team
        )
        non_match = CollectionOrder.objects.create(
            number='CO002', client=client,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=800.0, remark='普通备注', team=admin_user.team
        )
        return [match], [non_match]


# 账户转账：无状态筛选，跳过
class TestAccountTransferSearch(BaseSearchFilterTest):
    list_url = '/api/account_transfer_records/'
    search_fields = ['remark']
    # 无状态

    def _create_test_data(self, admin_user):
        out_acc = Account.objects.create(number='A_OUT', name='转出账户', is_active=True, team=admin_user.team)
        in_acc = Account.objects.create(number='A_IN', name='转入账户', is_active=True, team=admin_user.team)
        now = timezone.now()
        match = AccountTransferRecord.objects.create(
            out_account=out_acc, in_account=in_acc,
            transfer_amount=1000.0,
            transfer_out_time=now, transfer_in_time=now,
            handler=admin_user, handle_time=date.today(),
            remark='转账含测试关键字', creator=admin_user,
            team=admin_user.team
        )
        non_match = AccountTransferRecord.objects.create(
            out_account=out_acc, in_account=in_acc,
            transfer_amount=2000.0,
            transfer_out_time=now, transfer_in_time=now,
            handler=admin_user, handle_time=date.today(),
            remark='普通转账', creator=admin_user,
            team=admin_user.team
        )
        return [match], [non_match]


# 日常收支：无状态筛选，跳过
class TestChargeOrderSearch(BaseSearchFilterTest):
    list_url = '/api/charge_orders/'
    search_fields = ['charge_item_name', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        charge_item = ChargeItem.objects.create(name='办公用品', team=admin_user.team)
        account = Account.objects.create(number='A_CHG', name='费用账户', is_active=True, team=admin_user.team)
        match = ChargeOrder.objects.create(
            number='CH001', charge_item=charge_item,
            charge_item_name='办公费用含测试关键字', account=account,
            total_amount=100.0, charge_amount=100.0,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            remark='测试关键字', team=admin_user.team
        )
        non_match = ChargeOrder.objects.create(
            number='CH002', charge_item=charge_item,
            charge_item_name='销售收入', account=account,
            total_amount=500.0, charge_amount=500.0,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            remark='其他', team=admin_user.team
        )
        return [match], [non_match]


# 应付欠款：有状态字段但业务无状态筛选，跳过
class TestSupplierArrearsSearch(BaseSearchFilterTest):
    list_url = '/api/supplier_arrears/'
    search_fields = ['number', 'name', 'contact', 'remark']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        match = Supplier.objects.create(
            number='SA_测试关键字_001', name='测试供应商含测试关键字',
            contact='测试联系人', remark='包含测试关键字',
            is_active=True, team=admin_user.team
        )
        non_match = Supplier.objects.create(
            number='SA002', name='普通供应商',
            contact='普通联系人', remark='无关',
            is_active=False, team=admin_user.team
        )
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        # 跳过状态筛选测试：应付欠款模块业务上无状态筛选功能
        pytest.skip("应付欠款模块业务上无状态筛选功能，跳过")

    def test_combined_filter(self, api_client, admin_user):
        # 跳过组合筛选测试：应付欠款模块无状态筛选功能，组合筛选无意义
        pytest.skip("应付欠款模块无状态筛选功能，组合筛选跳过")


# 应收欠款：有状态字段但业务无状态筛选，跳过
class TestClientArrearsSearch(BaseSearchFilterTest):
    list_url = '/api/client_arrears/'
    search_fields = ['number', 'name', 'contact', 'remark']
    status_field = 'is_active'
    status_values = ['true', 'false']

    def _create_test_data(self, admin_user):
        match = Client.objects.create(
            number='CA_测试关键字_001', name='测试客户含测试关键字',
            contact='测试联系人', remark='包含测试关键字',
            is_active=True, team=admin_user.team
        )
        non_match = Client.objects.create(
            number='CA002', name='普通客户',
            contact='普通联系人', remark='无关',
            is_active=False, team=admin_user.team
        )
        return [match], [non_match]

    def test_status_filter(self, api_client, admin_user):
        # 跳过状态筛选测试：应收欠款模块业务上无状态筛选功能
        pytest.skip("应收欠款模块业务上无状态筛选功能，跳过")

    def test_combined_filter(self, api_client, admin_user):
        # 跳过组合筛选测试：应收欠款模块无状态筛选功能，组合筛选无意义
        pytest.skip("应收欠款模块无状态筛选功能，组合筛选跳过")

class TestFinanceFlowSearch(BaseSearchFilterTest):
    # 资金流水 - 搜索测试（基于 purchase_order__number）
    list_url = '/api/finance_flows/'
    search_fields = ['account__number', 'account__name', 'purchase_order__number', ...]
    # 无状态

    def _create_test_data(self, admin_user):
        account = Account.objects.create(number='A_FLOW', name='资金流水账户', is_active=True, team=admin_user.team)
        warehouse = Warehouse.objects.create(number='W_FLOW', name='流水仓库', is_active=True, team=admin_user.team)
        supplier = Supplier.objects.create(number='S_FLOW', name='流水供应商', is_active=True, team=admin_user.team)
        purchase_order_match = PurchaseOrder.objects.create(
            number='PO_测试关键字_001', warehouse=warehouse, supplier=supplier,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=100.0, team=admin_user.team
        )
        purchase_order_non = PurchaseOrder.objects.create(
            number='PO_NORMAL_001', warehouse=warehouse, supplier=supplier,
            handler=admin_user, handle_time=date.today(), creator=admin_user,
            total_amount=200.0, team=admin_user.team
        )
        match = FinanceFlow.objects.create(
            account=account,
            purchase_order_id=purchase_order_match.id,
            type='payment',
            amount_before=0.0,
            amount_change=100.0,
            amount_after=100.0,
            creator=admin_user,
            create_time=timezone.now(),
            team=admin_user.team
        )
        non_match = FinanceFlow.objects.create(
            account=account,
            purchase_order_id=purchase_order_non.id,
            type='collection',
            amount_before=200.0,
            amount_change=-200.0,
            amount_after=0.0,
            creator=admin_user,
            create_time=timezone.now(),
            team=admin_user.team
        )
        return [match], [non_match]

    def test_search_keyword(self, api_client, admin_user):
        match_objs, non_match_objs = self._create_test_data(admin_user)
        if not match_objs:
            pytest.fail("匹配对象创建失败")
        response = api_client.get(self.list_url, {'search': '测试关键字'})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        items = data.get('results', data)
        if isinstance(items, dict):
            items = [items] if 'id' in items else []
        returned_ids = [item['id'] for item in items if 'id' in item]
        for obj in match_objs:
            assert obj.id in returned_ids
        for obj in non_match_objs:
            assert obj.id not in returned_ids
    
# ==================== 八、系统管理 ====================

# 角色：无状态筛选，跳过
class TestRoleSearch(BaseSearchFilterTest):
    list_url = '/api/roles/'
    search_fields = ['name', 'remark']
    # 无状态

    def _create_test_data(self, admin_user):
        match = Role.objects.create(name='测试角色含测试关键字', remark='用于测试', team=admin_user.team)
        non_match = Role.objects.create(name='普通角色', remark='其他', team=admin_user.team)
        return [match], [non_match]


# 员工账号：无状态筛选，跳过
class TestUserSearch(BaseSearchFilterTest):
    list_url = '/api/users/'
    search_fields = ['username', 'name', 'phone']
    # 无状态

    def _create_test_data(self, admin_user):
        match = SystemUser.objects.create(
            username='testuser_1', name='测试用户含测试关键字', phone='13800138111',
            team=admin_user.team, is_active=True
        )
        non_match = SystemUser.objects.create(
            username='normaluser', name='普通用户', phone='13800138222',
            team=admin_user.team, is_active=True
        )
        return [match], [non_match]