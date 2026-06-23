from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.accounts.models import User
from .serializers import LoginSerializer, UserProfileSerializer, SetPasswordSerializer
from .services import OnboardingService
from apps.employees.models import Employee



class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            # Distinguish between missing fields (400) and bad credentials (401)
            errors = serializer.errors
            non_field_errors = errors.get('non_field_errors', [])
            if any('Invalid credentials' in str(e) for e in non_field_errors):
                return Response(
                    {'detail': 'Invalid credentials.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        tokens = serializer.get_tokens(user)
        return Response(tokens, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TriggerOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, erpnext_employee_id):
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.HR_ADMIN):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        service = OnboardingService()
        try:
            service.trigger(erpnext_employee_id, request.user)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Onboarding email sent."}, status=status.HTTP_200_OK)


class BulkTriggerOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.HR_ADMIN):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        service = OnboardingService()
        result = service.trigger_bulk(request.user)
        return Response(result, status=status.HTTP_200_OK)


class SetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            OnboardingService.set_password(
                token=serializer.validated_data['token'],
                password=serializer.validated_data['password'],
                password_confirm=serializer.validated_data['password_confirm'],
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Password set successfully."}, status=status.HTTP_200_OK)


class ResendOnboardingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, erpnext_employee_id):
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.HR_ADMIN):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        service = OnboardingService()
        try:
            service.resend(erpnext_employee_id, request.user)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Onboarding email resent."}, status=status.HTTP_200_OK)