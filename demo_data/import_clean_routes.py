import os
import sys
import csv
import io
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.models import BusStop, Route, RouteStop, Bus, BusLocation
from django.utils import timezone
from demo_data.import_filtered_routes import KNOWN_STOPS, haversine_km, get_or_create_stop

def run_clean_import():
    print("=== DELETING ALL EXISTING BUS ROUTES, ROUTE STOPS, AND BUSES ===")
    BusLocation.objects.all().delete()
    Bus.objects.all().delete()
    RouteStop.objects.all().delete()
    Route.objects.all().delete()
    print("Database cleared successfully.")

    csv_file = 'demo_data/nwkrtc_routes_all_629.csv'
    if not os.path.exists(csv_file):
        csv_file = 'demo_data/nwkrtc_routes_complete.csv'

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        routes_count = 0
        buses_count = 0

        for row in reader:
            bus_no = row['bus_no'].strip()
            route_name_raw = row['route_name'].strip()
            stops_str = row['stops_name_between_route'].strip()

            stops_list = [s.strip() for s in stops_str.split('→') if s.strip()]
            if not stops_list:
                continue

            start_stop_name = stops_list[0][:150]
            end_stop_name = stops_list[-1][:150]
            full_route_name = f"Route {bus_no}: {start_stop_name} ➔ {end_stop_name}"[:150]

            route_obj, _ = Route.objects.get_or_create(
                route_name=full_route_name,
                defaults={
                    'start_point': start_stop_name,
                    'end_point': end_stop_name,
                    'description': f"NWKRTC / BRTS Bus Route {bus_no} ({start_stop_name} to {end_stop_name})"
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

            routes_count += 1

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
            if not b_created:
                bus_obj.bus_number = bus_num_unique
                bus_obj.bus_name = f"NWKRTC Bus {bus_no} ({start_stop_name} ➔ {end_stop_name})"
                bus_obj.bus_type = bus_type_choice
                bus_obj.tracking_status = 'LIVE'
                bus_obj.is_active = True
                bus_obj.save()

            buses_count += 1

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

        print(f"SUCCESS! Imported {routes_count} clean Bus Routes & {buses_count} Buses.")
        print(f"Total Bus Stops in DB: {BusStop.objects.count()}")

if __name__ == '__main__':
    run_clean_import()
