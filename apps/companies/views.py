from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Company
from .serializers import CompanySerializer
from .permissions import IsSuperAdmin
from .services import CompanyService


class CompanyListView(generics.ListAPIView):
    """
    Super Admin views all registered companies.
    Companies are never created here — they come from ERPNext sync.
    """
    queryset = Company.objects.all().order_by('-created_at')
    serializer_class = CompanySerializer
    permission_classes = (IsSuperAdmin,)


class CompanyRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update local config fields only.
    ERPNext-owned fields (name, erpnext_doc_name) are read-only.
    """
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