import os
import sys
import csv
import io

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
import django
django.setup()

from tracking.models import BusStop, Route, RouteStop, Bus, BusLocation
from django.utils import timezone
from demo_data.import_filtered_routes import KNOWN_STOPS, haversine_km, get_or_create_stop

csv_file = 'demo_data/nwkrtc_routes_all_629.csv'
if not os.path.exists(csv_file):
    csv_file = 'demo_data/nwkrtc_routes_complete.csv'

print(f"Reading CSV file: {csv_file}")

total_rows_read = 0
unique_routes = {}
failed_records = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
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
                failed_records.append((row_idx, row, "Empty stop list"))
                continue

            key = (bus_no, route_name_raw, stops_str)
            if key in unique_routes:
                continue

            unique_routes[key] = {
                'bus_no': bus_no,
                'route_name_raw': route_name_raw,
                'stops_str': stops_str,
                'stops_list': stops_list
            }
        except Exception as e:
            failed_records.append((row_idx, row, str(e)))

total_unique_routes_found = len(unique_routes)

# Delete existing routes & buses
print("Deleting all existing bus routes, route stops, and buses...")
BusLocation.objects.all().delete()
Bus.objects.all().delete()
RouteStop.objects.all().delete()
Route.objects.all().delete()
print("Database cleared successfully.")

# Process routes
processed_routes_count = 0

for key, item in unique_routes.items():
    bus_no = item['bus_no']
    route_name_raw = item['route_name_raw']
    stops_list = item['stops_list']

    start_stop_name = stops_list[0][:150]
    end_stop_name = stops_list[-1][:150]
    full_route_name = f"Route {bus_no}: {start_stop_name} ➔ {end_stop_name}"[:150]

    route_obj, created = Route.objects.get_or_create(
        route_name=full_route_name,
        defaults={
            'start_point': start_stop_name,
            'end_point': end_stop_name,
            'description': f"NWKRTC / BRTS Bus Route {bus_no} ({route_name_raw})"
        }
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

    processed_routes_count += 1

    bus_type_choice = 'BRTS' if 'BRTS' in full_route_name or '100B' in bus_no or '200A' in bus_no else 'ORDINARY'

    bus_num_unique = bus_no
    suffix = 1
    while Bus.objects.filter(bus_number=bus_num_unique).exclude(route=route_obj).exists():
        suffix += 1
        bus_num_unique = f"{bus_no}-{suffix}"

    bus_obj, b_created = Bus.objects.get_or_create(
        route=route_obj,
        defaults={
            'bus_number': bus_num_unique,
            'bus_name': f"NWKRTC Bus {bus_no} ({start_stop_name} ➔ {end_stop_name})",
            'bus_type': bus_type_choice,
            'tracking_status': 'LIVE',
            'is_active': True
        }
    )

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

# Summary & Integrity Check
print("\n==========================================")
print("PROCESSING SUMMARY & DATA INTEGRITY METRICS:")
print(f"Total rows read: {total_rows_read}")
print(f"Total unique routes found: {total_unique_routes_found}")
print(f"Total routes processed: {processed_routes_count}")
print(f"Number of skipped or failed records: {len(failed_records)}")

db_route_count = Route.objects.count()
db_bus_count = Bus.objects.count()

print(f"\nDB Route Count Verification: {db_route_count} (Expected: {total_unique_routes_found})")
print(f"DB Bus Count Verification: {db_bus_count}")

if db_route_count == total_unique_routes_found:
    print("\nSUCCESS CRITERIA MET: 100% Data Integrity Verified!")
else:
    print("\nINTEGRITY FAILURE: Route count mismatch!")
print("==========================================")
