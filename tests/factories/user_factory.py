import factory
from factory import Faker, Sequence, SubFactory, LazyFunction
from django.contrib.auth.hashers import make_password
from apps.accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.LazyFunction(lambda: make_password("testpassword123"))
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    role = User.Role.EMPLOYEE
    is_onboarded = True
    company = None
    erpnext_employee_id = factory.Sequence(lambda n: f"EMP-{n:04d}")