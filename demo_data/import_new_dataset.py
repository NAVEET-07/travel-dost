import os
import sys
import csv
import math
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.models import BusStop, Route, RouteStop, Bus, BusLocation, BusTrackingSession, Fare, User
from tracking.services.distance import haversine_distance
from django.utils import timezone

def infer_area(stop_name):
    name_lower = stop_name.lower()
    if 'dharwad' in name_lower or '- dh' in name_lower or '-d' in name_lower:
        return 'Dharwad'
    if 'hubballi' in name_lower or 'hubli' in name_lower or '- hd' in name_lower or '-h' in name_lower or 'cbt' in name_lower:
        return 'Hubballi'
    if 'hosur' in name_lower:
        return 'Hosur'
    if 'vidya nagar' in name_lower or 'bvb' in name_lower:
        return 'Vidya Nagar'
    if 'gokul' in name_lower:
        return 'Gokul Road'
    if 'unkal' in name_lower:
        return 'Unkal'
    if 'saptapura' in name_lower:
        return 'Saptapura'
    if 'navanagar' in name_lower:
        return 'Navanagar'
    if 'rayapur' in name_lower:
        return 'Rayapur'
    if 'keshwapur' in name_lower:
        return 'Keshwapur'
    if 'old hubli' in name_lower:
        return 'Old Hubballi'
    if 'sattur' in name_lower:
        return 'Sattur'
    if 'mummigatti' in name_lower:
        return 'Mummigatti'
    if 'garag' in name_lower:
        return 'Garag'
    if 'byahatti' in name_lower:
        return 'Byahatti'
    return 'Hubballi-Dharwad'

def run_import():
    csv_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'demo_data', 'all_user_bus_routes.csv')
    print(f"Reading dataset from: {csv_file_path}")

    route_data = {}
    stop_data = {}

    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bno = row['bus_no'].strip()
            seq = int(row['stop_sequence'].strip())
            sname = row['stop_name'].strip()
            lat = float(row['lat'].strip())
            lon = float(row['lon'].strip())

            if bno not in route_data:
                route_data[bno] = []
            route_data[bno].append((seq, sname, lat, lon))
            if sname not in stop_data:
                stop_data[sname] = (lat, lon)

    print(f"Found {len(route_data)} bus routes and {len(stop_data)} unique bus stops.")

    print("\n--- Clearing existing database records ---")
    BusLocation.objects.all().delete()
    BusTrackingSession.objects.all().delete()
    Fare.objects.all().delete()
    RouteStop.objects.all().delete()
    Route.objects.all().delete()
    Bus.objects.all().delete()
    BusStop.objects.all().delete()
    print("Database cleared.\n")

    # 1. Create BusStop records
    print("--- Creating BusStop records ---")
    stop_objects = {}
    stops_to_create = []
    for sname, (lat, lon) in stop_data.items():
        area = infer_area(sname)
        stop_obj = BusStop(
            stop_name=sname,
            area=area,
            latitude=lat,
            longitude=lon,
            is_active=True
        )
        stops_to_create.append(stop_obj)

    BusStop.objects.bulk_create(stops_to_create)
    for s_obj in BusStop.objects.all():
        stop_objects[s_obj.stop_name] = s_obj

    print(f"Successfully created {len(stop_objects)} BusStop records.\n")

    # Driver assignment helper
    driver_user = User.objects.filter(role='DRIVER').first()

    # 2. Create Routes, RouteStops, and Buses
    print("--- Creating Route, RouteStop, and Bus records ---")
    routes_created = 0
    route_stops_created = 0
    buses_created = 0

    sorted_bno_list = sorted(route_data.keys())

    for idx, bno in enumerate(sorted_bno_list, 1):
        stops_seq = route_data[bno]
        stops_seq.sort(key=lambda x: x[0])

        start_name = stops_seq[0][1][:150]
        end_name = stops_seq[-1][1][:150]
        route_title = f"Route {bno}: {start_name} ➔ {end_name}"[:150]

        shape_geo = [[lat, lon] for _, _, lat, lon in stops_seq]

        route_obj = Route.objects.create(
            route_name=route_title,
            start_point=start_name,
            end_point=end_name,
            description=f"NWKRTC Transit Route {bno} ({start_name} to {end_name})",
            shape_geometry=shape_geo,
            is_active=True
        )
        routes_created += 1

        # RouteStops
        cumulative_dist = 0.0
        prev_lat, prev_lon = None, None
        rs_list = []

        for seq, sname, lat, lon in stops_seq:
            if prev_lat is not None and prev_lon is not None:
                d = haversine_distance(prev_lat, prev_lon, lat, lon)
                cumulative_dist += max(0.1, round(d, 3))
            prev_lat, prev_lon = lat, lon

            stop_obj = stop_objects[sname]
            rs_list.append(RouteStop(
                route=route_obj,
                bus_stop=stop_obj,
                stop_order=seq,
                distance_from_start_km=round(cumulative_dist, 2)
            ))

        RouteStop.objects.bulk_create(rs_list)
        route_stops_created += len(rs_list)

        # Bus
        is_brts = 'brts' in bno.lower() or 'chigari' in bno.lower()
        bus_type = 'BRTS' if is_brts else ('EXPRESS' if 'exp' in bno.lower() else 'ORDINARY')
        # Mark first 25 buses as LIVE for active map tracking demo
        is_live = (idx <= 25)
        tracking_status = 'LIVE' if is_live else 'OFFLINE'

        bus_number_str = f"KA-25-F-{bno}" if not bno.startswith('KA') else bno

        bus_obj = Bus.objects.create(
            bus_number=bus_number_str,
            bus_name=f"NWKRTC Bus {bno}",
            bus_type=bus_type,
            route=route_obj,
            driver=driver_user if (bno == '101' or idx == 1) else None,
            is_active=True,
            tracking_enabled=True,
            tracking_status=tracking_status
        )
        buses_created += 1

        if is_live and len(stops_seq) > 0:
            mid_idx = len(stops_seq) // 2
            mid_stop = stops_seq[mid_idx]
            BusLocation.objects.create(
                bus=bus_obj,
                latitude=mid_stop[2],
                longitude=mid_stop[3],
                speed=32.5,
                heading=90.0,
                timestamp=timezone.now()
            )

    print(f"\n==========================================")
    print("IMPORT COMPLETE SUMMARY:")
    print(f"Total BusStops: {BusStop.objects.count()}")
    print(f"Total Routes: {Route.objects.count()}")
    print(f"Total RouteStops: {RouteStop.objects.count()}")
    print(f"Total Buses: {Bus.objects.count()}")
    print(f"Total Live BusLocations: {BusLocation.objects.count()}")
    print(f"==========================================\n")

if __name__ == '__main__':
    run_import()
