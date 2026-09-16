import pytest
import re
from io import BytesIO
from openpyxl import Workbook, load_workbook
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.hashers import make_password
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.manage.models import SuperUser
from apps.system.models import User as SystemUser, Team
from apps.goods.models import Goods, GoodsCategory, GoodsUnit
from apps.data.models import Client, Supplier, Warehouse, Account, ChargeItem


# ==================== 辅助函数 ====================

# 下载导入模板并返回 openpyxl Workbook 对象
def download_template(api_client, template_url):
    response = api_client.get(template_url)
    assert response.status_code == status.HTTP_200_OK
    return load_workbook(BytesIO(response.content))


# 填充模板数据并上传导入
# - wb: 下载的模板 Workbook
# - data_dicts: 字典列表，每个字典的 key 为列名（支持简化名称），value 为要填入的值
def fill_template_and_upload(api_client, upload_url, wb, data_dicts):
    ws = wb.active
    headers = [cell.value for cell in ws[1]]

    # 提取核心列名：去除括号及括号内内容（支持中英文括号、方括号、尖括号等）
    def extract_core(name):
        if name is None:
            return ""
        return re.sub(r'[（(【\[<].*?[）)\]】>]', '', name).strip()

    # 建立核心名称到列索引的映射（列号从1开始）
    col_map = {}
    for idx, header in enumerate(headers, start=1):
        core = extract_core(header)
        col_map[core] = idx

    # 将数据按行写入模板（从第2行开始）
    for row_idx, row_data in enumerate(data_dicts, start=2):
        for col_name, value in row_data.items():
            core = extract_core(col_name)
            if core in col_map:
                ws.cell(row=row_idx, column=col_map[core], value=value)
            else:
                # 打印警告便于调试，但不中断流程
                print(f"警告：模板中未找到列 '{col_name}' (核心名: {core})")

    # 保存 Workbook 到内存流
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    # 构造上传文件对象
    file = SimpleUploadedFile(
        "import_data.xlsx",
        file_stream.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # 发送 multipart/form-data 请求
    return api_client.post(upload_url, {'file': file}, format='multipart')


# 创建 Excel 文件流（用于异常测试，如格式错误、表头缺失等）
def create_excel_file(headers, data_rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)          # 写入表头
    for row in data_rows:
        ws.append(row)          # 写入数据行
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return SimpleUploadedFile(
        "test_import.xlsx",
        file_stream.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# 创建非法格式文件（非 Excel，如 .txt），用于测试文件类型校验
def create_invalid_format_file():
    return SimpleUploadedFile(
        "test.txt",
        b"Invalid file content",
        content_type="text/plain"
    )


# ==================== Fixtures ====================

# 管理员用户（超级用户）
@pytest.fixture
def admin_user(db):
    # 创建团队
    team, _ = Team.objects.get_or_create(
        number='T001',
        defaults={'expiry_time': '2099-12-31', 'user_quantity': 100}
    )
    # 创建 SuperUser（用于认证）
    superuser, _ = SuperUser.objects.get_or_create(
        username='管理员',
        defaults={'password': make_password('123456')}
    )
    # 创建系统用户（关联团队，且为管理员）
    SystemUser.objects.get_or_create(
        id=superuser.id,
        defaults={
            'username': '管理员', 'name': '管理员', 'team': team,
            'is_active': True, 'is_manager': True, 'password': superuser.password,
        }
    )
    return superuser


# 管理员 JWT Token
@pytest.fixture
def admin_token(admin_user):
    return str(AccessToken.for_user(admin_user))


# 已认证的管理员 API 客户端
@pytest.fixture
def api_client(admin_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
    return client


# 普通用户（非管理员）的 Token，用于越权测试
@pytest.fixture
def regular_user_token(admin_user):
    system_admin = SystemUser.objects.get(id=admin_user.id)
    team = system_admin.team
    superuser = SuperUser(username='test_user')
    superuser.set_password('123456')
    superuser.save()
    SystemUser.objects.create(
        id=superuser.id,
        username='test_user', name='测试用户', team=team,
        is_active=True, is_manager=False, password=superuser.password,
    )
    return str(AccessToken.for_user(superuser))


# 测试用的产品分类（电子产品）
@pytest.fixture
def test_category(db, admin_user):
    system_admin = SystemUser.objects.get(id=admin_user.id)
    team = system_admin.team
    category, _ = GoodsCategory.objects.get_or_create(
        name='电子产品', defaults={'team': team}
    )
    return category


# 测试用的产品单位（个）
@pytest.fixture
def test_unit(db, admin_user):
    system_admin = SystemUser.objects.get(id=admin_user.id)
    team = system_admin.team
    unit, _ = GoodsUnit.objects.get_or_create(
        name='个', defaults={'team': team}
    )
    return unit


# 预先存在的产品（编号 G001），用于唯一性冲突测试
@pytest.fixture
def existing_goods(db, admin_user, test_category, test_unit):
    system_admin = SystemUser.objects.get(id=admin_user.id)
    team = system_admin.team
    goods, _ = Goods.objects.get_or_create(
        number='G001',
        defaults={
            'name': '已存在产品', 'category': test_category, 'unit': test_unit,
            'purchase_price': 100.0, 'retail_price': 150.0, 'team': team
        }
    )
    return goods


# ==================== 产品信息导入测试（9条） ====================

@pytest.mark.django_db
class TestGoodsImport:

    # TC-API-083：正向导入，只填充必填字段（编号、名称、激活状态）
    def test_import_goods_success(self, api_client):
        wb = download_template(api_client, '/api/goods/import_template/')
        data = [
            {"产品编号": "G002", "产品名称": "测试产品1", "激活状态": "TRUE"},
            {"产品编号": "G003", "产品名称": "测试产品2", "激活状态": "TRUE"},
        ]
        response = fill_template_and_upload(api_client, '/api/goods/import_data/', wb, data)
        # 成功应返回 204，且数据存在
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Goods.objects.filter(number='G002').exists()
        assert Goods.objects.filter(number='G003').exists()

    # TC-API-084：必填项缺失（产品名称为空），应全量回滚，返回400
    def test_import_goods_missing_required(self, api_client):
        wb = download_template(api_client, '/api/goods/import_template/')
        # 第二条记录产品名称为空，导致整批失败
        data = [
            {"产品编号": "G004", "产品名称": "测试产品4", "分类": "电子产品", "单位": "个", "采购价": "100", "零售价": "150"},
            {"产品编号": "G005", "产品名称": "", "分类": "电子产品", "单位": "个", "采购价": "200", "零售价": "250"},
            {"产品编号": "G006", "产品名称": "测试产品6", "分类": "电子产品", "单位": "个", "采购价": "300", "零售价": "350"},
        ]
        response = fill_template_and_upload(api_client, '/api/goods/import_data/', wb, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 所有数据均不应创建
        assert not Goods.objects.filter(number='G004').exists()
        assert not Goods.objects.filter(number='G005').exists()
        assert not Goods.objects.filter(number='G006').exists()

    # TC-API-085：数据格式错误（采购价非数字），应全量回滚
    def test_import_goods_invalid_format(self, api_client):
        headers = ["产品编号", "产品名称", "分类", "单位", "采购价", "零售价"]
        data = [["G007", "测试产品7", "电子产品", "个", "ABC", "150"]]
        file = create_excel_file(headers, data)
        response = api_client.post('/api/goods/import_data/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Goods.objects.filter(number='G007').exists()

    # TC-API-086：唯一性冲突（编号G001已存在），应全量回滚，返回400
    def test_import_goods_duplicate_number(self, api_client, existing_goods):
        wb = download_template(api_client, '/api/goods/import_template/')
        # 第一条记录编号重复，第二条合法但整批应回滚
        data = [
            {"产品编号": "G001", "产品名称": "重复产品", "激活状态": "TRUE"},
            {"产品编号": "G009", "产品名称": "测试产品9", "激活状态": "TRUE"},
        ]
        response = fill_template_and_upload(api_client, '/api/goods/import_data/', wb, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Goods.objects.filter(number='G009').exists()

    # TC-API-087：外键不存在（分类不存在），应全量回滚
    def test_import_goods_invalid_foreign_key(self, api_client):
        wb = download_template(api_client, '/api/goods/import_template/')
        data = [
            {"产品编号": "G010", "产品名称": "测试产品10", "分类": "不存在的分类", "单位": "个", "采购价": "100", "零售价": "150"},
            {"产品编号": "G011", "产品名称": "测试产品11", "分类": "不存在的分类", "单位": "个", "采购价": "200", "零售价": "250"},
        ]
        response = fill_template_and_upload(api_client, '/api/goods/import_data/', wb, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Goods.objects.filter(number='G010').exists()

    # TC-API-088：表头错误（缺少“产品名称”），应返回400
    def test_import_goods_invalid_header(self, api_client):
        headers = ["产品编号", "分类", "单位", "采购价"]  # 缺少"产品名称"
        data = [["G012", "电子产品", "个", "100"]]
        file = create_excel_file(headers, data)
        response = api_client.post('/api/goods/import_data/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Goods.objects.filter(number='G012').exists()

    # TC-API-089：空文件校验，应返回400
    def test_import_goods_empty_file(self, api_client):
        wb = Workbook()
        file_stream = BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)
        file = SimpleUploadedFile("empty.xlsx", file_stream.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = api_client.post('/api/goods/import_data/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # TC-API-090：非法文件格式（.txt），应返回400，实际抛出500，暴露缺陷
    def test_import_goods_invalid_file_type(self, api_client):
        file = create_invalid_format_file()
        response = api_client.post('/api/goods/import_data/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # TC-API-091：未登录访问，应返回401
    def test_import_goods_unauthenticated(self):
        client = APIClient()
        headers = ["产品编号", "产品名称", "分类", "单位", "采购价", "零售价"]
        data = [["G013", "测试产品13", "电子产品", "个", "100", "150"]]
        file = create_excel_file(headers, data)
        response = client.post('/api/goods/import_data/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # TC-API-092：非管理员越权访问，应返回403
    def test_import_goods_unauthorized_user(self, regular_user_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        headers = ["产品编号", "产品名称", "分类", "单位", "采购价", "零售价"]
        data = [["G014", "测试产品14", "电子产品", "个", "100", "150"]]
        file = create_excel_file(headers, data)
        response = client.post('/api/goods/import_data/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==================== 其他模块导入测试（7条） ====================

@pytest.mark.django_db
class TestOtherModulesImport:

    # TC-API-093：客户导入正向验证
    def test_import_client_success(self, api_client):
        wb = download_template(api_client, '/api/clients/import_template/')
        data = [
            {"客户编号": "C001", "客户名称": "测试客户1", "联系人": "张经理", "手机号": "13800138001"},
            {"客户编号": "C002", "客户名称": "测试客户2", "联系人": "李经理", "手机号": "13800138002"},
        ]
        response = fill_template_and_upload(api_client, '/api/clients/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Client.objects.filter(number='C001').exists()
        assert Client.objects.filter(number='C002').exists()

    # TC-API-094：客户导入必填项缺失（名称为空）
    def test_import_client_missing_required(self, api_client):
        wb = download_template(api_client, '/api/clients/import_template/')
        data = [
            {"客户编号": "C003", "客户名称": "", "联系人": "张经理", "手机号": "13800138003"},
            {"客户编号": "C004", "客户名称": "测试客户4", "联系人": "李经理", "手机号": "13800138004"},
        ]
        response = fill_template_and_upload(api_client, '/api/clients/import_data/', wb, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Client.objects.filter(number='C003').exists()
        assert not Client.objects.filter(number='C004').exists()

    # TC-API-093：供应商导入正向验证
    def test_import_supplier_success(self, api_client):
        wb = download_template(api_client, '/api/suppliers/import_template/')
        data = [
            {"供应商编号": "S001", "供应商名称": "测试供应商1", "联系人": "王经理", "电话": "13800138005"},
            {"供应商编号": "S002", "供应商名称": "测试供应商2", "联系人": "赵经理", "电话": "13800138006"},
        ]
        response = fill_template_and_upload(api_client, '/api/suppliers/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Supplier.objects.filter(number='S001').exists()
        assert Supplier.objects.filter(number='S002').exists()

    # TC-API-094：供应商导入必填项缺失（名称为空）
    def test_import_supplier_missing_required(self, api_client):
        wb = download_template(api_client, '/api/suppliers/import_template/')
        data = [
            {"供应商编号": "S003", "供应商名称": "", "联系人": "王经理", "电话": "13800138007"},
            {"供应商编号": "S004", "供应商名称": "测试供应商4", "联系人": "赵经理", "电话": "13800138008"},
        ]
        response = fill_template_and_upload(api_client, '/api/suppliers/import_data/', wb, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Supplier.objects.filter(number='S003').exists()
        assert not Supplier.objects.filter(number='S004').exists()

    # TC-API-095：仓库导入正向验证
    def test_import_warehouse_success(self, api_client):
        wb = download_template(api_client, '/api/warehouses/import_template/')
        data = [
            {"仓库编号": "W001", "仓库名称": "北京仓", "地址": "北京市朝阳区", "负责人": "张主管"},
            {"仓库编号": "W002", "仓库名称": "上海仓", "地址": "上海市浦东新区", "负责人": "李主管"},
        ]
        response = fill_template_and_upload(api_client, '/api/warehouses/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Warehouse.objects.filter(number='W001').exists()
        assert Warehouse.objects.filter(number='W002').exists()

    # TC-API-096：结算账户导入正向验证
    def test_import_account_success(self, api_client):
        wb = download_template(api_client, '/api/accounts/import_template/')
        data = [
            {"账户编号": "A001", "账户名称": "微信账户", "账户类型": "微信钱包"},
            {"账户编号": "A002", "账户名称": "银行账户", "账户类型": "银行账户"},
        ]
        response = fill_template_and_upload(api_client, '/api/accounts/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Account.objects.filter(number='A001').exists()
        assert Account.objects.filter(number='A002').exists()

    # TC-API-097：收支项目导入正向验证（列名：收支项目、收支类型）
    def test_import_charge_item_success(self, api_client):
        wb = download_template(api_client, '/api/charge_items/import_template/')
        data = [
            {"收支项目": "办公费用", "收支类型": "income"},
            {"收支项目": "销售收入", "收支类型": "income"},
        ]
        response = fill_template_and_upload(api_client, '/api/charge_items/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ChargeItem.objects.filter(name='办公费用').exists()
        assert ChargeItem.objects.filter(name='销售收入').exists()

    # TC-API-098：产品分类导入正向验证
    def test_import_goods_category_success(self, api_client):
        wb = download_template(api_client, '/api/goods_categories/import_template/')
        data = [
            {"分类名称": "电子产品", "备注": "手机、电脑等"},
            {"分类名称": "办公用品", "备注": "文具、耗材等"},
        ]
        response = fill_template_and_upload(api_client, '/api/goods_categories/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert GoodsCategory.objects.filter(name='电子产品').exists()
        assert GoodsCategory.objects.filter(name='办公用品').exists()

    # TC-API-099：产品单位导入正向验证
    def test_import_goods_unit_success(self, api_client):
        wb = download_template(api_client, '/api/goods_units/import_template/')
        data = [
            {"单位名称": "个", "备注": "基本单位"},
            {"单位名称": "箱", "备注": "包装单位"},
        ]
        response = fill_template_and_upload(api_client, '/api/goods_units/import_data/', wb, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert GoodsUnit.objects.filter(name='个').exists()
        assert GoodsUnit.objects.filter(name='箱').exists()


# ==================== 导出测试（6条） ====================

@pytest.mark.django_db
class TestExport:

    # TC-API-100：客户导出验证
    def test_export_clients(self, api_client):
        response = api_client.get('/api/clients/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('Content-Type', '').startswith('application/vnd.ms-excel')

    # 供应商导出
    def test_export_suppliers(self, api_client):
        response = api_client.get('/api/suppliers/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('Content-Type', '').startswith('application/vnd.ms-excel')

    # 仓库导出
    def test_export_warehouses(self, api_client):
        response = api_client.get('/api/warehouses/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('Content-Type', '').startswith('application/vnd.ms-excel')

    # 结算账户导出
    def test_export_accounts(self, api_client):
        response = api_client.get('/api/accounts/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('Content-Type', '').startswith('application/vnd.ms-excel')

    # 收支项目导出
    def test_export_charge_items(self, api_client):
        response = api_client.get('/api/charge_items/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('Content-Type', '').startswith('application/vnd.ms-excel')

    # 产品导出
    def test_export_goods(self, api_client):
        response = api_client.get('/api/goods/export/')
        assert response.status_code == status.HTTP_200_OK
        assert response.get('Content-Type', '').startswith('application/vnd.ms-excel')