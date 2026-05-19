from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'role',
        'company',
        'is_onboarded',
        'is_active',
    )

    list_filter = (
        'role',
        'is_onboarded',
        'is_active',
    )

    search_fields = (
        'username',
        'email',
        'erpnext_employee_id',
    )

    fieldsets = (
        *(UserAdmin.fieldsets or ()),
        (
            'Attendance System',
            {
                'fields': (
                    'role',
                    'company',
                    'erpnext_employee_id',
                    'is_onboarded',
                    'onboarding_token',
                    'onboarding_token_expires_at',
                )
            },
        ),
    )