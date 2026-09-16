import pytest
from django.contrib.auth.hashers import check_password
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.manage.models import SuperUser
from apps.system.models import User as SystemUser


# ==================== Fixtures ====================

@pytest.fixture
def regular_user(db, admin_user):
    # 创建普通用户（非管理员），SystemUser 密码与 SuperUser 同步
    team = admin_user.team

    superuser = SuperUser(username='testuser')
    superuser.set_password('oldpassword123')
    superuser.save()

    system_user = SystemUser(
        id=superuser.id,
        username='testuser',
        name='测试用户',
        password=superuser.password,
        team=team,
        is_active=True,
        is_manager=False,
    )
    system_user.save()

    return system_user, superuser


@pytest.fixture
def regular_user_token(regular_user):
    _, superuser = regular_user
    return str(AccessToken.for_user(superuser))


@pytest.fixture
def admin_token(admin_user):
    # 管理员 JWT Token（超级用户名为"管理员"）
    superuser = SuperUser.objects.get(id=admin_user.id)
    return str(AccessToken.for_user(superuser))


# ==================== 修改密码测试 ====================

@pytest.mark.django_db
class TestChangePassword:

    def test_change_password_success(self, regular_user, regular_user_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')

        url = '/api/user/set_password/'
        data = {
            'old_password': 'oldpassword123',
            'new_password': 'newpassword456',
        }
        response = client.post(url, data, format='json')

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

        # 验证 SystemUser 密码已更新（接口只更新 SystemUser）
        system_user, _ = regular_user
        system_user.refresh_from_db()
        assert check_password('newpassword456', system_user.password) is True

    def test_change_password_wrong_old_password(self, regular_user, regular_user_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')

        url = '/api/user/set_password/'
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword456',
        }
        response = client.post(url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_msg = str(response.data).lower()
        assert '密码错误' in error_msg

    def test_change_password_unauthenticated(self):
        client = APIClient()
        url = '/api/user/set_password/'
        data = {
            'old_password': 'oldpassword123',
            'new_password': 'newpassword456',
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_change_password_empty_new_password(self, regular_user, regular_user_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        url = '/api/user/set_password/'
        data = {
            'old_password': 'oldpassword123',
            'new_password': '',  # 空密码
        }
        response = client.post(url, data, format='json')
        # 预期返回 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 验证错误信息包含相关提示（根据实际后端返回调整关键词）
        error_msg = str(response.data).lower()
        # 常见提示关键词：不能为空、required、blank、null
        assert any(keyword in error_msg for keyword in ['不能为空', 'required', 'blank', '密码']), \
            f"错误信息未包含预期提示，实际返回：{error_msg}"


# ==================== 重置密码测试 ====================

@pytest.mark.django_db
class TestResetPassword:

    def test_reset_password_success(self, regular_user, admin_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')

        system_user, _ = regular_user
        url = f'/api/users/{system_user.id}/reset_password/'
        response = client.post(url, format='json')

        assert response.status_code == status.HTTP_200_OK

        # 验证 SystemUser 密码已被重置为 '123456'
        system_user.refresh_from_db()
        assert check_password('123456', system_user.password) is True

    def test_reset_password_user_not_found(self, admin_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
        url = '/api/users/99999/reset_password/'
        response = client.post(url, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reset_password_unauthorized_user(self, regular_user, regular_user_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        system_user, _ = regular_user
        url = f'/api/users/{system_user.id}/reset_password/'
        response = client.post(url, format='json')
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_reset_password_unauthenticated(self):
        client = APIClient()
        url = '/api/users/1/reset_password/'
        response = client.post(url, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reset_password_old_token_valid(self, regular_user, regular_user_token, admin_token):
        # 验证重置密码后旧 Token 仍然有效（系统未实现 Token 黑名单机制）。
        system_user, _ = regular_user

        # 先用旧 Token 访问需要认证的接口，确认有效
        client_regular = APIClient()
        client_regular.credentials(HTTP_AUTHORIZATION=f'Bearer {regular_user_token}')
        info_response = client_regular.get('/api/user/info/')
        assert info_response.status_code == status.HTTP_200_OK

        # 管理员重置密码
        client_admin = APIClient()
        client_admin.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
        reset_url = f'/api/users/{system_user.id}/reset_password/'
        reset_response = client_admin.post(reset_url, format='json')
        assert reset_response.status_code == status.HTTP_200_OK

        # 旧 Token 依然有效（系统未实现 Token 失效机制）
        info_response = client_regular.get('/api/user/info/')
        assert info_response.status_code == status.HTTP_200_OK