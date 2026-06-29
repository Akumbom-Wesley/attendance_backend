from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Company, GeofenceSite
from .serializers import CompanySerializer, GeofenceSiteSerializer, GeofenceSiteMobileSerializer
from .permissions import IsSuperAdmin
from .services import CompanyService


class CompanyListView(generics.ListAPIView):
    queryset = Company.objects.all().order_by('-created_at')
    serializer_class = CompanySerializer
    permission_classes = (IsSuperAdmin,)


class CompanyRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = (IsSuperAdmin,)
    http_method_names = ['get', 'patch']


class CompanyDeactivateView(APIView):
    permission_classes = (IsSuperAdmin,)

    def post(self, request, pk):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response(
                {'detail': 'Company not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        try:
            CompanyService.deactivate(company)
            return Response(
                {'detail': 'Company deactivated.'},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class GeofenceSiteMobileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        site = GeofenceSite.objects.filter(
            company=company,
            is_active=True,
        ).first()

        if site is None:
            return Response(
                {'detail': 'No active geofence site found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = GeofenceSiteMobileSerializer(site)
        return Response(serializer.data)

class CompanyMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        if company is None:
            return Response(
                {"detail": "No company associated with your account."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CompanySerializer(company)
        return Response(serializer.data)
