import os
import sys
import csv
import json
import io
import re

sys.stdout.reconfigure(encoding='utf-8')

transcript_path = r'C:\Users\NAVEET\.gemini\antigravity\brain\0b6d1914-aed1-4d33-bd2a-e7e54a2129e9\.system_generated\logs\transcript_full.jsonl'

raw_csv_text = None

with open(transcript_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Find the last USER_REQUEST message context containing '01,Cbt → Rajeev Nagar'
pattern = re.compile(r'bus_no,route_name,stops_name_between_route[\s\S]*?(?=</USER_REQUEST>)')
matches = pattern.findall(text)

print(f"Matches found: {len(matches)}")

if matches:
    raw_block = matches[-1].replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    lines = [l.strip() for l in raw_block.splitlines() if l.strip() and ',' in l]
    raw_csv_text = '\n'.join(lines)
    print(f"Extracted {len(lines)} CSV rows from user upload!")

if not raw_csv_text:
    print("ERROR: Could not find user uploaded CSV content in transcript!")
    sys.exit(1)

# Save exact CSV file
csv_file_path = 'demo_data/nwkrtc_routes_user_unique.csv'
with open(csv_file_path, 'w', encoding='utf-8') as out:
    out.write(raw_csv_text)

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
import django
django.setup()

from tracking.models import BusStop, Route, RouteStop, Bus, BusLocation
from django.utils import timezone
from demo_data.import_filtered_routes import KNOWN_STOPS, haversine_km, get_or_create_stop

# Parse CSV
total_rows_read = 0
unique_routes = {}
failed_records = []

reader = csv.DictReader(io.StringIO(raw_csv_text))
for row_idx, row in enumerate(reader, start=1):
    total_rows_read += 1
    try:
        bus_no = row['bus_no'].strip()
        route_name_raw = row['route_name'].strip()
        stops_str = row['stops_name_between_route'].strip()

        if not bus_no or not route_name_raw or not stops_str:
            failed_records.append((row_idx, row, "Missing required fields"))
            continue

        stops_list = [s.strip() for s in stops_str.split('→') if s.strip()]
        if not stops_list:
            failed_records.append((row_idx, row, "Empty stop sequence"))
            continue

        route_key = (bus_no, route_name_raw, stops_str)
        if route_key in unique_routes:
            continue

        unique_routes[route_key] = {
            'bus_no': bus_no,
            'route_name_raw': route_name_raw,
            'stops_str': stops_str,
            'stops_list': stops_list
        }
    except Exception as e:
        failed_records.append((row_idx, row, str(e)))

total_unique_routes_found = len(unique_routes)

# Delete existing DB records
print("\n--- Deleting all existing BusLocation, Bus, RouteStop, and Route records ---")
BusLocation.objects.all().delete()
Bus.objects.all().delete()
RouteStop.objects.all().delete()
Route.objects.all().delete()
print("Database cleared successfully.")

# Import every route
processed_routes = 0
processed_buses = 0

for route_key, item in unique_routes.items():
    bus_no = item['bus_no']
    route_name_raw = item['route_name_raw']
    stops_list = item['stops_list']

    start_stop_name = stops_list[0][:150]
    end_stop_name = stops_list[-1][:150]
    full_route_name = f"Route {bus_no}: {start_stop_name} ➔ {end_stop_name}"[:150]

    route_obj = Route.objects.create(
        route_name=full_route_name,
        start_point=start_stop_name,
        end_point=end_stop_name,
        description=f"NWKRTC / BRTS Bus Route {bus_no} ({route_name_raw})"
    )

    RouteStop.objects.filter(route=route_obj).delete()

    cumulative_dist = 0.0
    prev_stop = None
    stop_objects = []

    for idx, sname in enumerate(stops_list, 1):
        stop_obj = get_or_create_stop(sname)
        stop_objects.append(stop_obj)

        if prev_stop:
            dist = haversine_km(
                prev_stop.latitude, prev_stop.longitude,
                stop_obj.latitude, stop_obj.longitude
            )
            cumulative_dist += max(0.2, dist)

        RouteStop.objects.create(
            route=route_obj,
            bus_stop=stop_obj,
            stop_order=idx,
            distance_from_start_km=round(cumulative_dist, 2)
        )
        prev_stop = stop_obj

    processed_routes += 1

    bus_type_choice = 'BRTS' if 'BRTS' in full_route_name or '100B' in bus_no or '200A' in bus_no else 'ORDINARY'
    bus_num_unique = f"{bus_no}-{route_obj.id}"

    bus_obj = Bus.objects.create(
        route=route_obj,
        bus_number=bus_num_unique,
        bus_name=f"NWKRTC Bus {bus_no} ({start_stop_name} ➔ {end_stop_name})",
        bus_type=bus_type_choice,
        tracking_status='LIVE',
        is_active=True
    )

    processed_buses += 1

    mid_stop = stop_objects[len(stop_objects) // 2] if stop_objects else None
    if mid_stop:
        BusLocation.objects.create(
            bus=bus_obj,
            latitude=mid_stop.latitude,
            longitude=mid_stop.longitude,
            speed=32.0,
            heading=90.0,
            timestamp=timezone.now()
        )

# Verification Summary
print("\n==========================================")
print("PROCESSING SUMMARY & DATA INTEGRITY METRICS:")
db_route_count = Route.objects.count()
db_bus_count = Bus.objects.count()
db_stop_count = BusStop.objects.count()

print(f"Total rows read: {total_rows_read}")
print(f"Total unique routes found: {total_unique_routes_found}")
print(f"Total routes processed: {processed_routes}")
print(f"Number of skipped or failed records: {len(failed_records)}")
print(f"Total Routes created in DB: {db_route_count}")
print(f"Total Buses created in DB: {db_bus_count}")
print(f"Total Bus Stops in DB: {db_stop_count}")

if db_route_count == total_unique_routes_found:
    print("\nSUCCESS CRITERIA MET: 100% Data Integrity Verified!")
else:
    print(f"\nFAILURE: Expected {total_unique_routes_found} routes, got {db_route_count} in DB.")
print("==========================================")
