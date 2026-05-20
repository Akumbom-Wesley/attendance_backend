import factory
from django.utils import timezone
from apps.checkins.models import CheckinRecord
from tests.factories.device_factory import DeviceBindingFactory


class CheckinRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CheckinRecord

    device_binding = factory.SubFactory(DeviceBindingFactory)
    log_type = CheckinRecord.LOG_TYPE_CHOICES[0][0]
    timestamp_gps = factory.LazyFunction(timezone.now)
    timestamp_device = factory.LazyFunction(timezone.now)
    sync_received_at = factory.LazyFunction(timezone.now)
    gps_lat_smoothed = factory.Faker(
        'pydecimal', left_digits=2, right_digits=6, positive=True
    )
    gps_lng_smoothed = factory.Faker(
        'pydecimal', left_digits=2, right_digits=6, positive=True
    )
    gps_accuracy_metres = factory.Faker('random_int', min=1, max=50)
    rssi_avg = factory.Faker('random_int', min=-90, max=-40)
    wifi_ssid = factory.Faker('bothify', text='Office-WiFi-??##')
    wifi_bssid = factory.Faker('bothify', text='??:??:??:??:??:??')
    wifi_band = '5GHz'
    biometric_passed = True
    is_flagged = False
    is_synced = False