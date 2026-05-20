import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories.user_factory import UserFactory
from tests.factories.company_factory import CompanyFactory


@pytest.mark.django_db
class TestEmployeeLogin:

    def test_login_success_returns_tokens(self, api_client):
        company = CompanyFactory()
        user = UserFactory(
            username='EMP-0001',
            erpnext_employee_id='EMP-0001',
            company=company,
            role='EMPLOYEE'
        )
        url = reverse('accounts:login')
        payload = {
            'erpnext_employee_id': 'EMP-0001',
            'password': 'testpassword123'
        }
        response = api_client.post(url, payload, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert 'role' in response.data
        assert 'user_id' in response.data

    def test_login_wrong_password_returns_401(self, api_client):
        user = UserFactory(username='EMP-0002', erpnext_employee_id='EMP-0002')
        url = reverse('accounts:login')
        payload = {
            'erpnext_employee_id': 'EMP-0002',
            'password': 'wrongpassword'
        }
        response = api_client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_employee_returns_401(self, api_client):
        url = reverse('accounts:login')
        payload = {
            'erpnext_employee_id': 'EMP-9999',
            'password': 'testpassword123'
        }
        response = api_client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_missing_fields_returns_400(self, api_client):
        url = reverse('accounts:login')
        payload = {'erpnext_employee_id': 'EMP-0001'}
        response = api_client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_user_cannot_login(self, api_client):
        user = UserFactory(
            username='EMP-0003',
            erpnext_employee_id='EMP-0003',
            is_active=False
        )
        url = reverse('accounts:login')
        payload = {
            'erpnext_employee_id': 'EMP-0003',
            'password': 'testpassword123'
        }
        response = api_client.post(url, payload, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenRefresh:

    def test_refresh_returns_new_access_token(self, api_client):
        user = UserFactory(username='EMP-0010', erpnext_employee_id='EMP-0010')
        # First login to get tokens
        login_url = reverse('accounts:login')
        login_response = api_client.post(login_url, {
            'erpnext_employee_id': 'EMP-0010',
            'password': 'testpassword123'
        }, format='json')
        refresh_token = login_response.data['refresh']

        # Now refresh
        refresh_url = reverse('accounts:token_refresh')
        response = api_client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_invalid_refresh_token_returns_401(self, api_client):
        url = reverse('accounts:token_refresh')
        response = api_client.post(url, {
            'refresh': 'invalid.token.here'
        }, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenVerify:

    def test_valid_token_returns_200(self, api_client):
        user = UserFactory(username='EMP-0020', erpnext_employee_id='EMP-0020')
        login_url = reverse('accounts:login')
        login_response = api_client.post(login_url, {
            'erpnext_employee_id': 'EMP-0020',
            'password': 'testpassword123'
        }, format='json')
        access_token = login_response.data['access']

        verify_url = reverse('accounts:token_verify')
        response = api_client.post(verify_url, {
            'token': access_token
        }, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_invalid_token_returns_401(self, api_client):
        url = reverse('accounts:token_verify')
        response = api_client.post(url, {
            'token': 'bad.token.value'
        }, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeEndpoint:

    def test_authenticated_user_gets_profile(self, api_client):
        company = CompanyFactory()
        user = UserFactory(
            username='EMP-0030',
            erpnext_employee_id='EMP-0030',
            company=company
        )
        api_client.force_authenticate(user=user)
        url = reverse('accounts:me')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['erpnext_employee_id'] == 'EMP-0030'
        assert response.data['role'] == user.role
        assert 'company' in response.data

    def test_unauthenticated_request_returns_401(self, api_client):
        url = reverse('accounts:me')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED