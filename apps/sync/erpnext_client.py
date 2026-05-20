"""
Thin HTTP wrapper around the ERPNext REST API.
No business logic — only auth, request building, and error surfacing.

Auth header: Authorization: token <api_key>:<api_secret>
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

COMPANY_FIELDS = '["name","company_name"]'
EMPLOYEE_FIELDS = '["name","employee_name","company","department","company_email","status"]'
PAGE_SIZE = 100


class ERPNextAPIError(Exception):
    """Raised when ERPNext returns a non-2xx response or unexpected payload."""
    pass


class ERPNextClient:
    """
    Stateless client — instantiate once, call as needed.
    All methods return plain dicts (parsed JSON data).
    """

    def __init__(self):
        self.base_url = settings.ERPNEXT_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": (
                f"token {settings.ERPNEXT_API_KEY}:{settings.ERPNEXT_API_SECRET}"
            ),
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        """
        Internal GET helper. Raises ERPNextAPIError on non-2xx.
        Returns parsed JSON dict.
        """
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error("ERPNext HTTP error: %s — %s", e, response.text)
            raise ERPNextAPIError(f"HTTP {response.status_code}: {response.text}") from e
        except requests.RequestException as e:
            logger.error("ERPNext request failed: %s", e)
            raise ERPNextAPIError(str(e)) from e

    # ------------------------------------------------------------------ #
    #  Company                                                             #
    # ------------------------------------------------------------------ #

    def get_companies(self, limit_start: int = 0) -> list[dict]:
        """
        Returns one page of Company records.
        Paginate by incrementing limit_start by PAGE_SIZE.
        """
        data = self._get(
            "/api/resource/Company",
            params={
                "fields": COMPANY_FIELDS,
                "limit": PAGE_SIZE,
                "limit_start": limit_start,
            },
        )
        return data.get("data", [])

    def get_company(self, erpnext_doc_name: str) -> dict:
        """Returns a single Company record by its ERPNext doc name."""
        data = self._get(f"/api/resource/Company/{erpnext_doc_name}")
        return data.get("data", {})

    # ------------------------------------------------------------------ #
    #  Employee                                                            #
    # ------------------------------------------------------------------ #

    def get_employees(self, limit_start: int = 0) -> list[dict]:
        """
        Returns one page of Employee records.
        Paginate by incrementing limit_start by PAGE_SIZE.
        """
        data = self._get(
            "/api/resource/Employee",
            params={
                "fields": EMPLOYEE_FIELDS,
                "limit": PAGE_SIZE,
                "limit_start": limit_start,
            },
        )
        return data.get("data", [])

    def get_employee(self, erpnext_employee_id: str) -> dict:
        """Returns a single Employee record by ERPNext employee ID."""
        data = self._get(f"/api/resource/Employee/{erpnext_employee_id}")
        return data.get("data", {})
    
    def _post(self, path: str, data: dict) -> dict:
        """
        Internal POST helper. Raises ERPNextAPIError on non-2xx.
        Returns parsed JSON dict.
        """
        url = f"{self.base_url}{path}"
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error("ERPNext HTTP error: %s — %s", e, response.text)
            raise ERPNextAPIError(f"HTTP {response.status_code}: {response.text}") from e
        except requests.RequestException as e:
            logger.error("ERPNext request failed: %s", e)
            raise ERPNextAPIError(str(e)) from e

    def create_employee_checkin(self, data: dict) -> dict:
        """
        Creates an Employee Checkin doc in ERPNext.
        data must contain: employee, time, log_type, device_id, skip_auto_attendance
        """
        result = self._post("/api/resource/Employee Checkin", {"data": data})
        return result.get("data", {})