import math
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.devices.models import DeviceBinding
from apps.checkins.models import CheckinRecord
from apps.audit.models import AuditLog
from apps.employees.models import EmployeeStatus
from apps.companies.models import GeofenceSite


def _serializable_payload(payload: dict) -> dict:
    return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))


class CheckinValidationService:

    GPS_DEVICE_MAX_DELTA = 300   # seconds
    GPS_SERVER_MAX_DELTA = 600   # seconds
    VALID_CHECKOUT_STATUSES = {"present", "break", "errand", "assignment"}

    def __init__(self, payload: dict, server_now=None):
        self.payload = payload
        self.server_now = server_now or timezone.now()
        self.device_binding = None
        self.employee = None
        self.matched_site = None

    # ------------------------------------------------------------------ #
    #  Entry point                                                         #
    # ------------------------------------------------------------------ #

    def run(self):
        """
        Execute the pipeline in strict order.
        Returns (http_status_code, response_data_dict).
        Always writes an AuditLog on every outcome.
        """

        # Step 1 — Device binding
        result = self._check_device_binding()
        if result:
            return result

        # Step 2 — Anti-spoofing
        result = self._check_antispoofing()
        if result:
            return result

        # Step 3 — Timestamp plausibility
        result = self._check_timestamps()
        if result:
            return result

        # Step 4 — GPS geofence
        result = self._check_geofence()
        if result:
            return result

        # Step 5 — Biometric
        result = self._check_biometric()
        if result:
            return result

        # Step 6 — Wi-Fi RSSI
        two_factor_only, result = self._check_wifi_rssi()
        if result:
            return result

        # Step 7 — Duplicate check
        result = self._check_duplicate()
        if result:
            return result

        # Step 8 — Log type validation
        result = self._check_log_type()
        if result:
            return result

        # Step 9 — Pass
        return self._pass(two_factor_only)

    # ------------------------------------------------------------------ #
    #  Pipeline steps                                                      #
    # ------------------------------------------------------------------ #

    def _check_device_binding(self):
        device_unique_id = self.payload.get("device_unique_id")
        try:
            binding = DeviceBinding.objects.select_related("employee__user").get(
                device_unique_id=device_unique_id,
                is_active=True,
            )
            self.device_binding = binding
            self.employee = binding.employee
            return None
        except DeviceBinding.DoesNotExist:
            self._write_audit_log(
                error_code="DEVICE_NOT_REGISTERED",
                final_decision="FAIL",
                biometric_result=False,
                geofence_result=False,
                rssi_result=False,
                antispoofing_result=False,
                wifi_available=False,
                two_factor_only=False,
            )
            return 403, {"detail": "Device not registered or inactive."}

    def _check_antispoofing(self):
        flags = self.payload.get("antispoofing_flags", {})

        if flags.get("mock_location"):
            self._write_audit_log(
                error_code="MOCK_LOCATION_DETECTED",
                final_decision="FAIL",
                biometric_result=False,
                geofence_result=False,
                rssi_result=False,
                antispoofing_result=False,
                wifi_available=True,
                two_factor_only=False,
            )
            return 403, {"detail": "Mock location detected."}

        if flags.get("is_rooted"):
            self._write_audit_log(
                error_code="ROOTED_DEVICE_DETECTED",
                final_decision="FAIL",
                biometric_result=False,
                geofence_result=False,
                rssi_result=False,
                antispoofing_result=False,
                wifi_available=True,
                two_factor_only=False,
            )
            return 403, {"detail": "Rooted device detected."}

        return None

    def _check_timestamps(self):
        ts_gps = self.payload["timestamp_gps"]
        ts_device = self.payload["timestamp_device"]

        gps_device_delta = abs((ts_gps - ts_device).total_seconds())
        gps_server_delta = abs((ts_gps - self.server_now).total_seconds())

        if gps_device_delta >= self.GPS_DEVICE_MAX_DELTA or gps_server_delta >= self.GPS_SERVER_MAX_DELTA:
            self._write_audit_log(
                error_code="TIMESTAMP_IMPLAUSIBLE",
                final_decision="FAIL",
                biometric_result=False,
                geofence_result=False,
                rssi_result=False,
                antispoofing_result=True,
                wifi_available=True,
                two_factor_only=False,
            )
            return 422, {"detail": "Timestamp implausible."}

        return None

    def _check_geofence(self):
        company = self.employee.company
        sites = GeofenceSite.objects.filter(company=company, is_active=True)

        lat = float(self.payload["gps_lat_smoothed"])
        lng = float(self.payload["gps_lng_smoothed"])

        for site in sites:
            distance = self._haversine(lat, lng, float(site.latitude), float(site.longitude))
            if distance <= site.radius_metres:
                self.matched_site = site
                return None

        self._write_audit_log(
            error_code="GEOFENCE_FAILED",
            final_decision="FAIL",
            biometric_result=False,
            geofence_result=False,
            rssi_result=False,
            antispoofing_result=True,
            wifi_available=True,
            two_factor_only=False,
        )
        return 422, {"detail": "Outside geofence."}

    def _check_biometric(self):
        if not self.payload.get("biometric_passed"):
            self._write_audit_log(
                error_code="BIOMETRIC_FAILED",
                final_decision="FAIL",
                biometric_result=False,
                geofence_result=True,
                rssi_result=False,
                antispoofing_result=True,
                wifi_available=True,
                two_factor_only=False,
            )
            return 422, {"detail": "Biometric check failed."}
        return None

    def _check_wifi_rssi(self):
        """Returns (two_factor_only: bool, error_tuple | None)."""
        wifi_band = self.payload.get("wifi_band", "UNAVAILABLE")

        if wifi_band == "UNAVAILABLE":
            return True, None

        site = self.matched_site
        rssi_avg = self.payload.get("rssi_avg")
        wifi_bssid = self.payload.get("wifi_bssid", "")

        rssi_ok = rssi_avg is not None and rssi_avg >= site.rssi_threshold
        bssid_ok = not site.wifi_bssid or wifi_bssid == site.wifi_bssid
        band_ok = not site.enforce_5ghz or wifi_band == "5GHz"

        if not (rssi_ok and bssid_ok and band_ok):
            self._write_audit_log(
                error_code="WIFI_RSSI_BELOW_THRESHOLD",
                final_decision="FAIL",
                biometric_result=True,
                geofence_result=True,
                rssi_result=False,
                antispoofing_result=True,
                wifi_available=True,
                two_factor_only=False,
            )
            return False, (422, {"detail": "Wi-Fi RSSI check failed."})

        return False, None

    def _check_duplicate(self):
        exists = CheckinRecord.objects.filter(
            device_binding=self.device_binding,
            timestamp_gps=self.payload["timestamp_gps"],
        ).exists()

        if exists:
            self._write_audit_log(
                error_code="ALREADY_CHECKED_IN",
                final_decision="FAIL",
                biometric_result=True,
                geofence_result=True,
                rssi_result=True,
                antispoofing_result=True,
                wifi_available=True,
                two_factor_only=False,
            )
            return 409, {"detail": "Duplicate check-in."}
        return None

    def _check_log_type(self):
        if self.payload.get("log_type") != "OUT":
            return None

        latest_status = (
            EmployeeStatus.objects.filter(employee=self.employee)
            .order_by("-changed_at")
            .first()
        )

        if not latest_status or latest_status.status not in self.VALID_CHECKOUT_STATUSES:
            self._write_audit_log(
                error_code="INVALID_LOG_TYPE",
                final_decision="FAIL",
                biometric_result=True,
                geofence_result=True,
                rssi_result=True,
                antispoofing_result=True,
                wifi_available=True,
                two_factor_only=False,
            )
            return 422, {"detail": "Cannot clock out without a prior clock in."}
        return None

    def _pass(self, two_factor_only: bool):
        from apps.checkins.tasks import push_checkin_to_erpnext

        record = CheckinRecord.objects.create(
            device_binding=self.device_binding,
            log_type=self.payload["log_type"],
            timestamp_gps=self.payload["timestamp_gps"],
            timestamp_device=self.payload["timestamp_device"],
            sync_received_at=self.server_now,
            gps_lat_smoothed=self.payload["gps_lat_smoothed"],
            gps_lng_smoothed=self.payload["gps_lng_smoothed"],
            gps_accuracy_metres=self.payload["gps_accuracy_metres"],
            rssi_avg=self.payload.get("rssi_avg"),
            wifi_ssid=self.payload.get("wifi_ssid", ""),
            wifi_bssid=self.payload.get("wifi_bssid", ""),
            wifi_band=self.payload.get("wifi_band", "UNAVAILABLE"),
            biometric_passed=self.payload.get("biometric_passed", False),
        )

        final_decision = "TWO_FACTOR_ONLY" if two_factor_only else "PASS"

        self._write_audit_log(
            error_code="SUCCESS",
            final_decision=final_decision,
            biometric_result=True,
            geofence_result=True,
            rssi_result=not two_factor_only,
            antispoofing_result=True,
            wifi_available=not two_factor_only,
            two_factor_only=two_factor_only,
            checkin_record=record,
        )

        push_checkin_to_erpnext.delay(record.id)

        return 201, {"id": record.id, "final_decision": final_decision}

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _write_audit_log(
        self,
        error_code,
        final_decision,
        biometric_result,
        geofence_result,
        rssi_result,
        antispoofing_result,
        wifi_available,
        two_factor_only,
        checkin_record=None,
    ):
        AuditLog.objects.create(
            checkin_record=checkin_record,
            employee=self.employee,
            biometric_result=biometric_result,
            geofence_result=geofence_result,
            rssi_result=rssi_result,
            antispoofing_result=antispoofing_result,
            wifi_available=wifi_available,
            two_factor_only=two_factor_only,
            error_code=error_code,
            final_decision=final_decision,
            gps_timestamp_used=self.payload.get("timestamp_gps") or self.server_now,
            raw_payload=_serializable_payload(self.payload),
        )

    @staticmethod
    def _haversine(lat1, lng1, lat2, lng2) -> float:
        """Returns distance in metres between two GPS coordinates."""
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))