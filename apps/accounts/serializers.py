from rest_framework import serializers
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class LoginSerializer(serializers.Serializer):
    erpnext_employee_id = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        erpnext_employee_id = data.get('erpnext_employee_id')
        password = data.get('password')

        try:
            user = User.objects.get(
                erpnext_employee_id=erpnext_employee_id,
                is_active=True
            )
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials.")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid credentials.")

        data['user'] = user
        return data

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role,
            'user_id': user.id,
        }


class UserProfileSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source='company.name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'erpnext_employee_id',
            'company',
            'company_name',
            'is_onboarded',
        )
        read_only_fields = fields