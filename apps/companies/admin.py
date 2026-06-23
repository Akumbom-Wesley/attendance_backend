from django.contrib import admin
from .models import Company, GeofenceSite

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'erpnext_doc_name', 'is_active', 'created_at')
    search_fields = ('name', 'erpnext_doc_name')
    list_filter = ('is_active',)

@admin.register(GeofenceSite)
class GeofenceSiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'radius_metres', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active', 'company')