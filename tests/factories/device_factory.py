import factory
from django.utils import timezone
from apps.devices.models import DeviceBinding
from tests.factories.employee_factory import EmployeeFactory


class DeviceBindingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeviceBinding

    employee = factory.SubFactory(EmployeeFactory)
    device_unique_id = factory.Sequence(lambda n: f"DEVICE-{n:08d}")
    attendance_device_id = factory.Sequence(lambda n: f"ATT-{n:08d}")
    is_active = True
    bound_at = factory.LazyFunction(timezone.now)
    unbound_at = None