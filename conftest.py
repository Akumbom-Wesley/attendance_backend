import pytest
from pytest_factoryboy import register
from tests.factories.user_factory import UserFactory
from tests.factories.company_factory import CompanyFactory
from tests.factories.employee_factory import EmployeeFactory
from tests.factories.device_factory import DeviceBindingFactory
from tests.factories.checkin_factory import CheckinRecordFactory


register(UserFactory)
register(CompanyFactory)
register(EmployeeFactory)
register(DeviceBindingFactory)
register(CheckinRecordFactory)


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client):
    def _authenticated_client(user):
        api_client.force_authenticate(user=user)
        return api_client
    return _authenticated_client