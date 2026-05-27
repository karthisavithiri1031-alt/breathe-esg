"""
Management script to seed the DB with realistic sample data.
Run: python manage.py shell < create_sample_data.py
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from emissions.models import Organisation, OrganisationMembership, EmissionFactorLibrary, FacilityLookup

# Create demo user
if not User.objects.filter(username="analyst").exists():
    u = User.objects.create_user("analyst", password="demo1234", email="analyst@demo.com")
    u.first_name = "Alex"
    u.last_name = "Analyst"
    u.save()
    Token.objects.get_or_create(user=u)
    print("Created user: analyst / demo1234")

user = User.objects.get(username="analyst")
token, _ = Token.objects.get_or_create(user=user)
print(f"Token: {token.key}")

# Create organisation
if not Organisation.objects.filter(slug="acme-corp").exists():
    org = Organisation.objects.create(name="Acme Corporation", slug="acme-corp")
    OrganisationMembership.objects.create(user=user, organisation=org, role="admin")
    print("Created org: Acme Corporation")

org = Organisation.objects.get(slug="acme-corp")

# Seed facility lookup
facilities = [
    {"sap_plant_code": "1000", "name": "Mumbai HQ", "country_code": "IN", "city": "Mumbai", "grid_region": "Western"},
    {"sap_plant_code": "1001", "name": "Delhi Office", "country_code": "IN", "city": "Delhi", "grid_region": "Northern"},
    {"sap_plant_code": "1002", "name": "Bangalore Tech Park", "country_code": "IN", "city": "Bangalore", "grid_region": "Southern"},
    {"sap_plant_code": "2000", "name": "London UK Office", "country_code": "GB", "city": "London", "grid_region": "GB"},
]
for f in facilities:
    FacilityLookup.objects.get_or_create(organisation=org, sap_plant_code=f["sap_plant_code"], defaults=f)
print("Seeded facility lookup")

# Seed emission factors
factors = [
    {"category": "fuel_combustion", "sub_category": "diesel", "region": "IN", "year": 2024, "factor": "2.51839", "unit": "litre", "source": "DEFRA"},
    {"category": "fuel_combustion", "sub_category": "petrol", "region": "IN", "year": 2024, "factor": "2.31380", "unit": "litre", "source": "DEFRA"},
    {"category": "purchased_electricity", "sub_category": "", "region": "IN", "year": 2024, "factor": "0.70800", "unit": "kWh", "source": "CEA"},
    {"category": "purchased_electricity", "sub_category": "", "region": "GB", "year": 2024, "factor": "0.20493", "unit": "kWh", "source": "DEFRA"},
    {"category": "business_travel_flight", "sub_category": "economy", "region": "", "year": 2024, "factor": "0.15553", "unit": "passenger_km", "source": "DEFRA"},
    {"category": "business_travel_flight", "sub_category": "business", "region": "", "year": 2024, "factor": "0.42875", "unit": "passenger_km", "source": "DEFRA"},
    {"category": "business_travel_hotel", "sub_category": "", "region": "", "year": 2024, "factor": "21.40", "unit": "room_night", "source": "DEFRA"},
]
for f in factors:
    EmissionFactorLibrary.objects.get_or_create(
        category=f["category"], sub_category=f["sub_category"],
        region=f["region"], year=f["year"], source=f["source"],
        defaults=f
    )
print("Seeded emission factors")
print(f"\n=== DEMO CREDENTIALS ===\nUsername: analyst\nPassword: demo1234\nToken: {token.key}\n")
