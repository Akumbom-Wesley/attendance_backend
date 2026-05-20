from .models import Company


class CompanyService:

    @staticmethod
    def deactivate(company: Company) -> Company:
        if not company.is_active:
            raise ValueError("Company is already inactive.")
        company.is_active = False
        company.save(update_fields=['is_active', 'updated_at'])
        return company

    @staticmethod
    def update_local_config(company: Company, validated_data: dict) -> Company:
        """
        Only updates fields we own locally — never erpnext_doc_name or name.
        Those are owned by ERPNext and updated only via sync.
        """
        allowed_fields = {'is_active', 'webhook_secret'}
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(company, field, value)
        company.save()
        return company