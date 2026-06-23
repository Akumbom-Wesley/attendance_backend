"""
apps/sync/services.py

ERPNext bulk import and per-record sync service.
Business logic lives here — not in views, not in serializers.
"""

import logging
from apps.sync.erpnext_client import ERPNextClient
from apps.companies.models import Company
from apps.employees.models import Employee
from apps.accounts.models import User

logger = logging.getLogger(__name__)


class ERPNextSyncService:

    def __init__(self):
        self.client = ERPNextClient()

    # ------------------------------------------------------------------ #
    #  Company                                                             #
    # ------------------------------------------------------------------ #

    def sync_company(self, erpnext_data: dict) -> Company:
        """
        Upsert a Company from an ERPNext data dict.
        Creates or updates based on erpnext_doc_name.
        """
        company, _ = Company.objects.update_or_create(
            erpnext_doc_name=erpnext_data["name"],
            defaults={
                "name": erpnext_data["company_name"],
                "is_active": True,
            },
        )
        return company

    # ------------------------------------------------------------------ #
    #  Employee                                                            #
    # ------------------------------------------------------------------ #

    def sync_employee(self, erpnext_data: dict) -> Employee:
        """
        Upsert an Employee (and its linked User) from an ERPNext data dict.
        Raises ValueError if the linked Company doesn't exist locally yet.
        """
        company_name = erpnext_data["company"]
        try:
            company = Company.objects.get(erpnext_doc_name=company_name)
        except Company.DoesNotExist:
            raise ValueError(f"Company '{company_name}' not found locally. Run company sync first.")

        erpnext_employee_id = erpnext_data["name"]
        full_name = erpnext_data["employee_name"]
        # Split full_name into first/last
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        email = erpnext_data.get("company_email") or ""
        department = erpnext_data.get("department") or ""
        is_active = erpnext_data.get("status") == "Active"

        # Upsert the User
        user, _ = User.objects.update_or_create(
            erpnext_employee_id=erpnext_employee_id,
            defaults={
                "username": erpnext_employee_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "company": company,
                "role": User.Role.EMPLOYEE,
                "is_onboarded": False,
            },
        )

        # Upsert the Employee profile
        employee, _ = Employee.objects.update_or_create(
            erpnext_employee_id=erpnext_employee_id,
            defaults={
                "user": user,
                "company": company,
                "full_name": full_name,
                "email": email,
                "department": department,
                "is_active": is_active,
            },
        )
        return employee

    # ------------------------------------------------------------------ #
    #  Bulk import                                                         #
    # ------------------------------------------------------------------ #

    def bulk_import(self) -> dict:
        """
        Paginate through all Companies and Employees in ERPNext
        and upsert them locally.
        Returns a summary dict: {companies_synced, employees_synced}
        """
        companies_synced = 0
        employees_synced = 0

        # --- Companies ---
        limit_start = 0
        while True:
            records = self.client.get_companies(limit_start=limit_start)
            if not records:
                break
            for record in records:
                self.sync_company(record)
                companies_synced += 1
            limit_start += len(records)

        # --- Employees ---
        limit_start = 0
        while True:
            records = self.client.get_employees(limit_start=limit_start)
            if not records:
                break
            for record in records:
                try:
                    self.sync_employee(record)
                    employees_synced += 1
                except ValueError as e:
                    logger.warning("Skipping employee %s: %s", record.get("name"), e)
            limit_start += len(records)

        return {
            "companies_synced": companies_synced,
            "employees_synced": employees_synced,
        }