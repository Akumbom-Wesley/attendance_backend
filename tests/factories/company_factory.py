import factory
from apps.companies.models import Company


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    erpnext_doc_name = factory.Sequence(lambda n: f"Company-{n:04d}")
    name = factory.Faker('company')
    webhook_secret = factory.Faker('uuid4')
    is_active = True