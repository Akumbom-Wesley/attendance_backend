from rest_framework.views import APIView
from django.views import View
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

from django.shortcuts import render

class SetPasswordPageView(View):
    def get(self, request):
        return render(request, 'onboarding/set_password.html')


class OnboardingStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.HR_ADMIN):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        qs = Employee.objects.all()
        if request.user.role == User.Role.HR_ADMIN:
            qs = qs.filter(company=request.user.company)

        total_onboarded = qs.filter(user__is_onboarded=True).count()
        total_no_email = qs.filter(email="").count()
        total_pending = qs.filter(user__is_onboarded=False).exclude(email="").count()

        return Response(
            {
                "total_onboarded": total_onboarded,
                "total_pending": total_pending,
                "total_no_email": total_no_email,
            },
            status=status.HTTP_200_OK,
        )


class OnboardingPendingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.HR_ADMIN):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        from apps.employees.serializers import EmployeeSerializer

        qs = Employee.objects.filter(user__is_onboarded=False).exclude(email="")
        if request.user.role == User.Role.HR_ADMIN:
            qs = qs.filter(company=request.user.company)
        qs = qs.order_by("full_name")

        # Manual pagination
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except ValueError:
            page, page_size = 1, 20

        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()
        results = qs[start:end]

        serializer = EmployeeSerializer(results, many=True)
        return Response(
            {
                "count": total,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class HRDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in (User.Role.SUPER_ADMIN, User.Role.HR_ADMIN):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        from django.utils import timezone
        from apps.checkins.models import CheckinRecord
        from apps.employees.models import EmployeeStatus

        today = timezone.now().date()

        employee_qs = Employee.objects.all()
        if request.user.role == User.Role.HR_ADMIN:
            employee_qs = employee_qs.filter(company=request.user.company)

        total_employees = employee_qs.filter(is_active=True).count()

        # Present today: employees with an approved IN checkin today and no OUT after it
        checked_in_today_ids = (
            CheckinRecord.objects.filter(
                device_binding__employee__in=employee_qs,
                log_type="IN",
                is_approved=False,
                is_rejected=False,
                timestamp_gps__date=today,
            )
            .values_list("device_binding__employee_id", flat=True)
            .distinct()
        )
        present_today = len(checked_in_today_ids)

        # Absent: active employees with no IN checkin today
        absent_today = total_employees - present_today

        # Flagged pending review
        flagged_pending = CheckinRecord.objects.filter(
            device_binding__employee__in=employee_qs,
            is_flagged=True,
            is_approved=False,
            is_rejected=False,
        ).count()

        # Not onboarded
        not_onboarded = employee_qs.filter(
            user__is_onboarded=False
        ).exclude(email="").count()

        return Response(
            {
                "present_today": present_today,
                "absent_today": absent_today,
                "flagged_pending": flagged_pending,
                "not_onboarded": not_onboarded,
                "total_active_employees": total_employees,
            },
            status=status.HTTP_200_OK,
        )
