from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from ingestion.views import (
    SourceFileViewSet, EmissionRecordViewSet, IngestViewSet,
    dashboard_summary, audit_log_list, register, login_view,
)

router = DefaultRouter()
router.register(r"source-files", SourceFileViewSet, basename="sourcefile")
router.register(r"records", EmissionRecordViewSet, basename="emissionrecord")
router.register(r"ingest", IngestViewSet, basename="ingest")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/dashboard/", dashboard_summary),
    path("api/audit-log/", audit_log_list),
    path("api/auth/register/", register),
    path("api/auth/login/", login_view),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
