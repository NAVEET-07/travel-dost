import os
import sys
import csv
import io

sys.stdout.reconfigure(encoding='utf-8')

# Read base forward routes
forward_routes = []
with open('demo_data/nwkrtc_routes_complete.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        bno = row['bus_no'].strip()
        rname = row['route_name'].strip()
        stops = row['stops_name_between_route'].strip()
        if bno and rname and stops:
            forward_routes.append((bno, rname, stops))

print(f"Loaded {len(forward_routes)} base forward routes.")

# Generate bidirectional dataset with user's '_2' naming convention
all_rows = [("bus_no", "route_name", "stops_name_between_route")]

for bno, rname, stops in forward_routes:
    stops_list = [s.strip() for s in stops.split('→') if s.strip()]
    if not stops_list:
        continue
    
    start_stop = stops_list[0]
    end_stop = stops_list[-1]
    
    # 1. Forward direction e.g. 100: Betdur → Hosur Terminal
    fwd_bno = bno
    fwd_rname = f"{start_stop} → {end_stop}"
    fwd_stops = stops
    all_rows.append((fwd_bno, fwd_rname, fwd_stops))
    
    # 2. Return direction with _2 suffix e.g. 100_2: Hosur Terminal → Betdur
    if not bno.endswith('_2'):
        rev_bno = f"{bno}_2"
    else:
        rev_bno = bno
        
    rev_rname = f"{end_stop} → {start_stop}"
    rev_stops = ' → '.join(reversed(stops_list))
    all_rows.append((rev_bno, rev_rname, rev_stops))

total_routes_generated = len(all_rows) - 1
print(f"Generated {total_routes_generated} routes with user's '_2' return naming format.")

# Save to demo_data/nwkrtc_routes_user_underscore2.csv
with open('demo_data/nwkrtc_routes_user_underscore2.csv', 'w', encoding='utf-8', newline='') as out:
    writer = csv.writer(out)
    writer.writerows(all_rows)

print("Saved demo_data/nwkrtc_routes_user_underscore2.csv!")

# Setup Django & Import into DB
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
import django
django.setup()

from tracking.models import BusStop, Route, RouteStop, Bus, BusLocation
from django.utils import timezone
from demo_data.import_filtered_routes import KNOWN_STOPS, haversine_km, get_or_create_stop

print("\n--- Clearing existing database records ---")
BusLocation.objects.all().delete()
Bus.objects.all().delete()
RouteStop.objects.all().delete()
Route.objects.all().delete()
print("Database cleared successfully.")

total_rows_read = 0
processed_routes = 0
processed_buses = 0
failed_records = []

with open('demo_data/nwkrtc_routes_user_underscore2.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row_idx, row in enumerate(reader, start=1):
        total_rows_read += 1
        try:
            bus_no = row['bus_no'].strip()
            route_name_raw = row['route_name'].strip()
            stops_str = row['stops_name_between_route'].strip()

            stops_list = [s.strip() for s in stops_str.split('→') if s.strip()]
            if not stops_list:
                failed_records.append((row_idx, row, "Empty stop list"))
                continue

            start_stop_name = stops_list[0][:150]
            end_stop_name = stops_list[-1][:150]
            full_route_name = f"Route {bus_no}: {start_stop_name} ➔ {end_stop_name}"[:150]

            route_obj = Route.objects.create(
                route_name=full_route_name,
                start_point=start_stop_name,
                end_point=end_stop_name,
                description=f"NWKRTC / BRTS Bus Route {bus_no} ({route_name_raw})"
            )

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
            
            bus_num_unique = bus_no
            suffix = 1
            while Bus.objects.filter(bus_number=bus_num_unique).exists():
                suffix += 1
                bus_num_unique = f"{bus_no}-{suffix}"

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

        except Exception as e:
            failed_records.append((row_idx, row, str(e)))

# Validation & Summary
print("\n==========================================")
print("FINAL EXECUTION & INTEGRITY SUMMARY:")
db_route_count = Route.objects.count()
db_bus_count = Bus.objects.count()
db_stop_count = BusStop.objects.count()

print(f"Total rows read: {total_rows_read}")
print(f"Total unique routes processed: {processed_routes}")
print(f"Number of failed/skipped records: {len(failed_records)}")
print(f"Total Routes in DB: {db_route_count}")
print(f"Total Buses in DB: {db_bus_count}")
print(f"Total Bus Stops in DB: {db_stop_count}")

if db_route_count == total_rows_read:
    print("\nSUCCESS: 100% Match! All routes imported with user '_2' return naming format.")
else:
    print("\nDISCREPANCY DETECTED!")
print("==========================================")
