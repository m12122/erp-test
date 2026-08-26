import os
import django
# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
# 显式启动 Django
django.setup()


import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

# 导入所需模型
from apps.system.models import Team, User as SystemUser
from apps.manage.models import SuperUser
from apps.goods.models import Goods, Inventory
from apps.data.models import Supplier, Warehouse


@pytest.fixture
def admin_user(db):
    # 创建团队
    team = Team.objects.create(
        number='T001',
        expiry_time=timezone.now() + timedelta(days=365),
        user_quantity=10,
    )

    # 创建 SuperUser（认证用户）
    superuser = SuperUser(username='管理员')
    superuser.set_password('123456')
    superuser.save()

    # 创建 SystemUser（业务用户），ID 与 SuperUser 相同
    system_user = SystemUser(
        id=superuser.id,
        username='管理员',
        name='管理员',
        team=team,
        is_active=True,
        is_manager=True,
    )
    system_user.save()

    return system_user  # 返回业务用户，供视图使用


@pytest.fixture
def api_client(admin_user):
    # 返回已认证的 API 客户端（使用 JWT）
    client = APIClient()
    # 通过 admin_user.id 获取对应的 SuperUser（ID 相同）
    superuser = SuperUser.objects.get(id=admin_user.id)
    token = AccessToken.for_user(superuser)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.fixture
def product_a(db, admin_user):
    # 创建产品 A（初始库存需单独创建）
    return Goods.objects.create(
        number='P001',
        name='产品A',
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
def warehouse_active(db, admin_user):
    # 创建激活状态的仓库
    return Warehouse.objects.create(
        number='W001',
        name='主仓库',
        is_active=True,
        team=admin_user.team,
    )


@pytest.fixture
def inventory_a(db, product_a, warehouse_active, admin_user):
    # 创建产品A在仓库中的初始库存 10
    return Inventory.objects.create(
        warehouse=warehouse_active,
        goods=product_a,
        total_quantity=10.0,
        has_stock=True,
        team=admin_user.team,
    )