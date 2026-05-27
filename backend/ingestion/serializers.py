from rest_framework import serializers
from emissions.models import SourceFile, EmissionRecord, AuditLog, Organisation


class SourceFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SourceFile
        fields = [
            "id", "source_type", "file_name", "status", "error_message",
            "row_count_raw", "row_count_parsed", "row_count_failed",
            "uploaded_at", "processed_at", "uploaded_by_name",
            "detected_encoding", "detected_delimiter",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return "System"


class EmissionRecordSerializer(serializers.ModelSerializer):
    source_file_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            "id", "scope", "category", "activity_date", "period_start", "period_end",
            "raw_quantity", "raw_unit", "raw_spend", "raw_currency",
            "normalised_quantity", "normalised_unit",
            "emission_factor", "emission_factor_source", "emission_factor_year",
            "co2e_kg",
            "facility_code", "facility_name", "country_code",
            "source_metadata", "validation_flags", "is_estimated", "estimation_note",
            "status", "reviewed_by_name", "reviewed_at", "review_note",
            "is_edited", "original_values",
            "created_at", "updated_at",
            "source_file", "source_file_name", "source_row_ref",
        ]
        read_only_fields = [
            "id", "co2e_kg", "scope", "category", "activity_date",
            "source_file", "source_row_ref", "created_at", "updated_at",
            "reviewed_by_name",
        ]

    def get_source_file_name(self, obj):
        return obj.source_file.file_name if obj.source_file else ""

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    """Restricted serializer for analyst edits — preserves original values."""

    class Meta:
        model = EmissionRecord
        fields = ["review_note", "facility_name", "country_code", "estimation_note"]

    def update(self, instance, validated_data):
        # Snapshot original values before first edit
        if not instance.is_edited:
            instance.original_values = {
                "facility_name": instance.facility_name,
                "country_code": instance.country_code,
                "estimation_note": instance.estimation_note,
                "review_note": instance.review_note,
            }
            instance.is_edited = True
        return super().update(instance, validated_data)


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "action", "target_type", "target_id", "detail", "timestamp", "actor_name"]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.username
        return "System"


class DashboardSummarySerializer(serializers.Serializer):
    total_co2e_kg = serializers.DecimalField(max_digits=18, decimal_places=2)
    scope_breakdown = serializers.DictField()
    category_breakdown = serializers.DictField()
    status_breakdown = serializers.DictField()
    records_total = serializers.IntegerField()
    records_flagged = serializers.IntegerField()
    records_approved = serializers.IntegerField()
    records_pending = serializers.IntegerField()
    source_files_count = serializers.IntegerField()
