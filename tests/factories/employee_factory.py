import factory
from apps.employees.models import Employee
from tests.factories.user_factory import UserFactory
from tests.factories.company_factory import CompanyFactory


class EmployeeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Employee

    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    erpnext_employee_id = factory.Sequence(lambda n: f"EMP-{n:04d}")
    full_name = factory.Faker('name')
    email = factory.Faker('email')
    department = factory.Faker('job')
    is_active = True