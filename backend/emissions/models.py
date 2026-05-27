"""
Core data model for Breathe ESG ingestion platform.

Design philosophy:
- EmissionRecord is the canonical "one row" that goes to auditors. Everything
  upstream exists to produce and justify a row here.
- SourceFile tracks every ingest artifact so we always know provenance.
- AuditLog is append-only — never deleted, never edited in place.
- Units are normalised to CO2e (kg) at write time; raw values preserved.
"""

from django.db import models
from django.contrib.auth.models import User
import uuid


class Organisation(models.Model):
    """Multi-tenancy root. Every data object foreign-keys here."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    ROLE_ANALYST = "analyst"
    ROLE_ADMIN = "admin"
    ROLE_AUDITOR = "auditor"
    ROLE_CHOICES = [
        (ROLE_ANALYST, "Analyst"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_AUDITOR, "Auditor (read-only)"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organisation")


class SourceFile(models.Model):
    SOURCE_SAP = "sap"
    SOURCE_UTILITY = "utility"
    SOURCE_TRAVEL = "travel"
    SOURCE_CHOICES = [
        (SOURCE_SAP, "SAP Export (Fuel/Procurement)"),
        (SOURCE_UTILITY, "Utility Data (Electricity)"),
        (SOURCE_TRAVEL, "Corporate Travel"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="source_files")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    file_name = models.CharField(max_length=500)
    file = models.FileField(upload_to="source_files/%Y/%m/", null=True, blank=True)
    raw_content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    row_count_raw = models.IntegerField(null=True, blank=True)
    row_count_parsed = models.IntegerField(null=True, blank=True)
    row_count_failed = models.IntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    detected_encoding = models.CharField(max_length=50, blank=True)
    detected_delimiter = models.CharField(max_length=10, blank=True)
    parser_version = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.source_type} | {self.file_name} | {self.status}"


class EmissionRecord(models.Model):
    SCOPE_CHOICES = [(1, "Scope 1"), (2, "Scope 2"), (3, "Scope 3")]

    CATEGORY_FUEL_COMBUSTION = "fuel_combustion"
    CATEGORY_PURCHASED_ELECTRICITY = "purchased_electricity"
    CATEGORY_BUSINESS_TRAVEL_FLIGHT = "business_travel_flight"
    CATEGORY_BUSINESS_TRAVEL_HOTEL = "business_travel_hotel"
    CATEGORY_BUSINESS_TRAVEL_GROUND = "business_travel_ground"
    CATEGORY_PROCUREMENT = "procurement"
    CATEGORY_CHOICES = [
        (CATEGORY_FUEL_COMBUSTION, "Fuel Combustion"),
        (CATEGORY_PURCHASED_ELECTRICITY, "Purchased Electricity"),
        (CATEGORY_BUSINESS_TRAVEL_FLIGHT, "Business Travel – Flight"),
        (CATEGORY_BUSINESS_TRAVEL_HOTEL, "Business Travel – Hotel"),
        (CATEGORY_BUSINESS_TRAVEL_GROUND, "Business Travel – Ground Transport"),
        (CATEGORY_PROCUREMENT, "Procurement"),
    ]

    STATUS_PENDING = "pending"
    STATUS_FLAGGED = "flagged"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_LOCKED = "locked"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Review"),
        (STATUS_FLAGGED, "Flagged"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_LOCKED, "Locked for Audit"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="emission_records")
    source_file = models.ForeignKey(SourceFile, on_delete=models.CASCADE, related_name="records")
    source_row_ref = models.CharField(max_length=200, blank=True)

    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)

    activity_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    raw_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    raw_unit = models.CharField(max_length=50)
    raw_currency = models.CharField(max_length=10, blank=True)
    raw_spend = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    normalised_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    normalised_unit = models.CharField(max_length=50)

    emission_factor = models.DecimalField(max_digits=18, decimal_places=6)
    emission_factor_source = models.CharField(max_length=200, blank=True)
    emission_factor_year = models.IntegerField(null=True, blank=True)

    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4)

    facility_code = models.CharField(max_length=100, blank=True)
    facility_name = models.CharField(max_length=255, blank=True)
    country_code = models.CharField(max_length=3, blank=True)

    source_metadata = models.JSONField(default=dict, blank=True)
    validation_flags = models.JSONField(default=list, blank=True)
    is_estimated = models.BooleanField(default=False)
    estimation_note = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="reviewed_records")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    is_edited = models.BooleanField(default=False)
    original_values = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-activity_date"]
        indexes = [
            models.Index(fields=["organisation", "scope", "activity_date"]),
            models.Index(fields=["organisation", "status"]),
            models.Index(fields=["source_file"]),
        ]

    def save(self, *args, **kwargs):
        if self.normalised_quantity and self.emission_factor:
            self.co2e_kg = self.normalised_quantity * self.emission_factor
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category} | {self.activity_date} | {self.co2e_kg} kgCO2e"


class AuditLog(models.Model):
    """Immutable event log. Only create(), never update()."""
    ACTION_CHOICES = [
        ("upload", "File Uploaded"),
        ("parse", "File Parsed"),
        ("approve", "Record Approved"),
        ("reject", "Record Rejected"),
        ("edit", "Record Edited"),
        ("lock", "Record Locked"),
        ("flag", "Record Auto-Flagged"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="audit_logs")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=30, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]


class FacilityLookup(models.Model):
    """Maps opaque SAP plant codes to human-readable facility info."""
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="facilities")
    sap_plant_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    country_code = models.CharField(max_length=3, blank=True)
    city = models.CharField(max_length=100, blank=True)
    grid_region = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("organisation", "sap_plant_code")


class EmissionFactorLibrary(models.Model):
    category = models.CharField(max_length=50)
    sub_category = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    year = models.IntegerField()
    factor = models.DecimalField(max_digits=18, decimal_places=6)
    unit = models.CharField(max_length=50)
    source = models.CharField(max_length=50)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("category", "sub_category", "region", "year", "source")
