from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decouple import config

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser from environment variables if one does not exist'

    def handle(self, *args, **kwargs):
        email = config('SUPERUSER_EMAIL', default=None)
        password = config('SUPERUSER_PASSWORD', default=None)
        erpnext_id = config('SUPERUSER_ERPNEXT_ID', default='SUPER-ADMIN-001')

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                'SUPERUSER_EMAIL or SUPERUSER_PASSWORD not set — skipping.'
            ))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(
                f'Superuser with email {email} already exists — skipping.'
            ))
            return

        User.objects.create_superuser(
            username=email,
            email=email,
            password=password,
            role='SUPER_ADMIN',
            erpnext_employee_id=erpnext_id,
            is_onboarded=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Superuser {email} created.'))
