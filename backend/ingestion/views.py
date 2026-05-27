import io
import csv
from decimal import Decimal
from datetime import datetime

from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser

from emissions.models import (
    SourceFile, EmissionRecord, AuditLog, Organisation, OrganisationMembership
)
from .serializers import (
    SourceFileSerializer, EmissionRecordSerializer,
    EmissionRecordUpdateSerializer, AuditLogSerializer,
    DashboardSummarySerializer,
)
from .parsers.sap_parser import parse_sap_csv
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser import parse_travel_csv


def get_user_org(request):
    """Get the first organisation the user belongs to."""
    membership = OrganisationMembership.objects.filter(user=request.user).select_related("organisation").first()
    if membership:
        return membership.organisation
    return None


def log_action(org, actor, action, target_type, target_id, detail=None):
    AuditLog.objects.create(
        organisation=org,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
    )


class SourceFileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SourceFileSerializer

    def get_queryset(self):
        org = get_user_org(self.request)
        if not org:
            return SourceFile.objects.none()
        return SourceFile.objects.filter(organisation=org).order_by("-uploaded_at")


class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        org = get_user_org(self.request)
        if not org:
            return EmissionRecord.objects.none()
        qs = EmissionRecord.objects.filter(organisation=org).select_related("source_file", "reviewed_by")

        scope = self.request.query_params.get("scope")
        if scope:
            qs = qs.filter(scope=scope)

        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        record_status = self.request.query_params.get("status")
        if record_status:
            qs = qs.filter(status=record_status)

        source_file = self.request.query_params.get("source_file")
        if source_file:
            qs = qs.filter(source_file_id=source_file)

        flagged = self.request.query_params.get("flagged")
        if flagged == "true":
            qs = qs.filter(validation_flags__len__gt=0)

        return qs

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return EmissionRecordUpdateSerializer
        return EmissionRecordSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        record = self.get_object()
        org = get_user_org(request)
        if record.status == EmissionRecord.STATUS_LOCKED:
            return Response({"error": "Record is locked for audit and cannot be changed."}, status=400)
        record.status = EmissionRecord.STATUS_APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_note = request.data.get("note", "")
        record.save()
        log_action(org, request.user, "approve", "emission_record", record.id,
                   {"note": record.review_note})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        record = self.get_object()
        org = get_user_org(request)
        if record.status == EmissionRecord.STATUS_LOCKED:
            return Response({"error": "Record is locked for audit and cannot be changed."}, status=400)
        record.status = EmissionRecord.STATUS_REJECTED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_note = request.data.get("note", "")
        record.save()
        log_action(org, request.user, "reject", "emission_record", record.id,
                   {"note": record.review_note})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        record = self.get_object()
        org = get_user_org(request)
        if record.status != EmissionRecord.STATUS_APPROVED:
            return Response({"error": "Only approved records can be locked."}, status=400)
        record.status = EmissionRecord.STATUS_LOCKED
        record.save()
        log_action(org, request.user, "lock", "emission_record", record.id, {})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=False, methods=["post"])
    def bulk_approve(self, request):
        org = get_user_org(request)
        ids = request.data.get("ids", [])
        records = EmissionRecord.objects.filter(
            organisation=org, id__in=ids
        ).exclude(status=EmissionRecord.STATUS_LOCKED)
        count = records.count()
        records.update(
            status=EmissionRecord.STATUS_APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        for r in records:
            log_action(org, request.user, "approve", "emission_record", r.id, {"bulk": True})
        return Response({"approved": count})


class IngestViewSet(viewsets.ViewSet):
    """Handles file upload + parsing."""
    parser_classes = [MultiPartParser, JSONParser]

    def create(self, request):
        org = get_user_org(request)
        if not org:
            return Response({"error": "No organisation found for user."}, status=400)

        source_type = request.data.get("source_type")
        if source_type not in ("sap", "utility", "travel"):
            return Response({"error": "source_type must be sap, utility, or travel"}, status=400)

        country_code = request.data.get("country_code", "default")

        # Accept file upload or raw text paste
        uploaded_file = request.FILES.get("file")
        raw_text = request.data.get("raw_content", "")

        if not uploaded_file and not raw_text:
            return Response({"error": "Provide a file or raw_content"}, status=400)

        # Read bytes BEFORE model.create so FileField.save() doesn't exhaust the stream
        pre_read_bytes = None
        if uploaded_file:
            pre_read_bytes = uploaded_file.read()
            uploaded_file.seek(0)

        with transaction.atomic():
            source_file = SourceFile.objects.create(
                organisation=org,
                uploaded_by=request.user,
                source_type=source_type,
                file_name=uploaded_file.name if uploaded_file else f"paste_{source_type}_{timezone.now().isoformat()}.csv",
                file=uploaded_file,
                raw_content=raw_text if not uploaded_file else "",
                status=SourceFile.STATUS_PROCESSING,
                parser_version="1.0.0",
            )
            log_action(org, request.user, "upload", "source_file", source_file.id,
                       {"file_name": source_file.file_name, "source_type": source_type})

            # Read content
            try:
                if uploaded_file:
                    raw_bytes = pre_read_bytes
                    # Detect encoding
                    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
                        try:
                            content = raw_bytes.decode(enc)
                            source_file.detected_encoding = enc
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        content = raw_bytes.decode("latin-1")
                        source_file.detected_encoding = "latin-1"
                else:
                    content = raw_text
                    source_file.detected_encoding = "utf-8"

                # Parse
                if source_type == "sap":
                    records_data, errors = parse_sap_csv(content, str(source_file.id), str(org.id))
                elif source_type == "utility":
                    records_data, errors = parse_utility_csv(content, str(source_file.id), str(org.id), country_code)
                else:
                    records_data, errors = parse_travel_csv(content, str(source_file.id), str(org.id))

                # Count raw rows (minus header)
                raw_lines = [l for l in content.strip().splitlines() if l.strip()]
                source_file.row_count_raw = max(0, len(raw_lines) - 1)
                source_file.row_count_parsed = len(records_data)
                source_file.row_count_failed = len(errors)

                # Create EmissionRecords
                created_records = []
                for rd in records_data:
                    rd.pop("_raw", None)

                    # Auto-flag if validation warnings exist
                    has_flags = bool(rd.get("validation_flags"))
                    record_status = EmissionRecord.STATUS_FLAGGED if has_flags else EmissionRecord.STATUS_PENDING

                    rec = EmissionRecord.objects.create(
                        organisation=org,
                        source_file=source_file,
                        status=record_status,
                        **rd,
                    )
                    created_records.append(rec)
                    if has_flags:
                        log_action(org, None, "flag", "emission_record", rec.id,
                                   {"flags": rd["validation_flags"]})

                source_file.status = SourceFile.STATUS_DONE
                source_file.processed_at = timezone.now()
                source_file.error_message = ""
                if errors:
                    source_file.error_message = f"{len(errors)} rows failed parsing. First error: {errors[0]['error']}"
                source_file.save()

                log_action(org, request.user, "parse", "source_file", source_file.id, {
                    "parsed": len(records_data),
                    "failed": len(errors),
                    "errors": errors[:5],  # log first 5 errors only
                })

                return Response({
                    "source_file": SourceFileSerializer(source_file).data,
                    "records_created": len(created_records),
                    "parse_errors": len(errors),
                    "parse_error_detail": errors[:10],
                }, status=201)

            except Exception as e:
                source_file.status = SourceFile.STATUS_FAILED
                source_file.error_message = str(e)
                source_file.save()
                return Response({"error": f"Parse failed: {str(e)}"}, status=500)


@api_view(["GET"])
def dashboard_summary(request):
    org = get_user_org(request)
    if not org:
        return Response({"error": "No organisation"}, status=400)

    records = EmissionRecord.objects.filter(organisation=org)

    total_co2e = records.aggregate(t=Sum("co2e_kg"))["t"] or Decimal("0")

    scope_breakdown = {}
    for s in [1, 2, 3]:
        val = records.filter(scope=s).aggregate(t=Sum("co2e_kg"))["t"] or Decimal("0")
        scope_breakdown[f"scope_{s}"] = float(val)

    category_breakdown = {}
    for cat, label in EmissionRecord.CATEGORY_CHOICES:
        val = records.filter(category=cat).aggregate(t=Sum("co2e_kg"))["t"] or Decimal("0")
        category_breakdown[cat] = {"label": label, "co2e_kg": float(val)}

    status_breakdown = {}
    for st, label in EmissionRecord.STATUS_CHOICES:
        count = records.filter(status=st).count()
        status_breakdown[st] = {"label": label, "count": count}

    return Response({
        "total_co2e_kg": float(total_co2e),
        "scope_breakdown": scope_breakdown,
        "category_breakdown": category_breakdown,
        "status_breakdown": status_breakdown,
        "records_total": records.count(),
        "records_flagged": records.filter(status=EmissionRecord.STATUS_FLAGGED).count(),
        "records_approved": records.filter(status=EmissionRecord.STATUS_APPROVED).count(),
        "records_pending": records.filter(status=EmissionRecord.STATUS_PENDING).count(),
        "source_files_count": SourceFile.objects.filter(organisation=org).count(),
    })


@api_view(["GET"])
def audit_log_list(request):
    org = get_user_org(request)
    if not org:
        return Response({"error": "No organisation"}, status=400)
    logs = AuditLog.objects.filter(organisation=org).select_related("actor")[:200]
    return Response(AuditLogSerializer(logs, many=True).data)


@api_view(["POST"])
def register(request):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    username = request.data.get("username")
    password = request.data.get("password")
    email = request.data.get("email", "")
    org_name = request.data.get("organisation", "Demo Organisation")

    if not username or not password:
        return Response({"error": "username and password required"}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username taken"}, status=400)

    user = User.objects.create_user(username=username, password=password, email=email)
    import re
    slug = re.sub(r'[^a-z0-9]+', '-', org_name.lower()).strip('-') or "org"
    base_slug = slug
    n = 1
    while Organisation.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    org = Organisation.objects.create(name=org_name, slug=slug)
    OrganisationMembership.objects.create(user=user, organisation=org, role="admin")
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "username": username, "organisation": org_name}, status=201)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_view(request):
    from django.contrib.auth import authenticate
    from rest_framework.authtoken.models import Token
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if not user:
        return Response({"error": "Invalid credentials"}, status=401)
    token, _ = Token.objects.get_or_create(user=user)
    org = get_user_org_for_user(user)
    return Response({
        "token": token.key,
        "username": username,
        "organisation": org.name if org else "",
        "organisation_id": str(org.id) if org else "",
    })


def get_user_org_for_user(user):
    membership = OrganisationMembership.objects.filter(user=user).select_related("organisation").first()
    return membership.organisation if membership else None


register.permission_classes = [permissions.AllowAny]
