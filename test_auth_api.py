import pytest
from rest_framework import status
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient

from apps.manage.models import SuperUser


# ==================== Fixtures ====================

@pytest.fixture
def superuser(db):
    # 创建测试超级用户 admin/123456
    user = SuperUser(username='admin')
    user.password = make_password('123456')
    user.save()
    return user


# ==================== Test Class ====================

@pytest.mark.django_db
class TestAuthAPI:

    # ========== TC-API-055 用户登录-正确账号验证 ==========
    def test_login_success(self, superuser):
        client = APIClient()
        url = '/api/super_user/login/'
        data = {
            'username': 'admin',
            'password': '123456',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # 验证 Session 已建立
        info_url = '/api/super_user/info/'
        info_response = client.get(info_url)
        assert info_response.status_code == status.HTTP_200_OK

    # ========== TC-API-056 用户登录-错误密码校验 ==========
    def test_login_wrong_password(self, superuser):
        client = APIClient()
        url = '/api/super_user/login/'
        data = {
            'username': 'admin',
            'password': 'wrong_password',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = str(response.data).lower()
        assert '账号密码错误' in error_msg or 'password' in error_msg