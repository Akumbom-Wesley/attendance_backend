import pytest
from django.urls import reverse
from rest_framework import status
from tests.factories.company_factory import CompanyFactory
from tests.factories.user_factory import UserFactory


@pytest.mark.django_db
class TestListCompanies:

    def test_superadmin_can_list_companies(self, api_client):
        CompanyFactory.create_batch(3)
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3

    def test_unauthenticated_cannot_list_companies(self, api_client):
        url = reverse('companies:company-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_employee_cannot_list_companies(self, api_client):
        user = UserFactory(role='EMPLOYEE')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestRetrieveCompany:

    def test_superadmin_can_retrieve_company(self, api_client):
        company = CompanyFactory()
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-detail', kwargs={'pk': company.pk})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == company.pk

    def test_webhook_secret_not_in_response(self, api_client):
        company = CompanyFactory()
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-detail', kwargs={'pk': company.pk})
        response = api_client.get(url)
        assert 'webhook_secret' not in response.data

    def test_retrieve_nonexistent_company_returns_404(self, api_client):
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-detail', kwargs={'pk': 99999})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestUpdateCompany:

    def test_superadmin_can_update_local_config(self, api_client):
        company = CompanyFactory(is_active=True)
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-detail', kwargs={'pk': company.pk})
        response = api_client.patch(url, {'is_active': False}, format='json')
        assert response.status_code == status.HTTP_200_OK

    def test_erpnext_doc_name_is_readonly(self, api_client):
        company = CompanyFactory(erpnext_doc_name='ORIGINAL')
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-detail', kwargs={'pk': company.pk})
        api_client.patch(url, {'erpnext_doc_name': 'HACKED'}, format='json')
        company.refresh_from_db()
        assert company.erpnext_doc_name == 'ORIGINAL'

    def test_hr_admin_cannot_update_company(self, api_client):
        company = CompanyFactory()
        user = UserFactory(role='HR_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-detail', kwargs={'pk': company.pk})
        response = api_client.patch(url, {'is_active': False}, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestDeactivateCompany:

    def test_superadmin_can_deactivate_company(self, api_client):
        company = CompanyFactory(is_active=True)
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-deactivate', kwargs={'pk': company.pk})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        company.refresh_from_db()
        assert company.is_active is False

    def test_deactivate_already_inactive_returns_400(self, api_client):
        company = CompanyFactory(is_active=False)
        user = UserFactory(role='SUPER_ADMIN')
        api_client.force_authenticate(user=user)
        url = reverse('companies:company-deactivate', kwargs={'pk': company.pk})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST