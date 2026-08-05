import csv
import io
import math
from django.core.management.base import BaseCommand
from tracking.models import BusStop, Route, RouteStop, Bus, BusLocation
from django.utils import timezone
from demo_data.import_filtered_routes import RAW_USER_BUS_ROUTES_DATA, KNOWN_STOPS, haversine_km, get_or_create_stop

class Command(BaseCommand):
    help = 'Imports real filtered NWKRTC bus stops and routes dataset into Travel Dost.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('=== NWKRTC / BRTS Filtered Data Importer ==='))
        
        reader = csv.DictReader(io.StringIO(RAW_USER_BUS_ROUTES_DATA.strip()))
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
            
            bus_obj, b_created = Bus.objects.get_or_create(
                bus_number=bus_no,
                defaults={
                    'bus_name': f"NWKRTC Bus {bus_no} ({route_name_raw})",
                    'bus_type': bus_type_choice,
                    'route': route_obj,
                    'tracking_status': 'LIVE',
                    'is_active': True
                }
            )
            if not b_created:
                bus_obj.route = route_obj
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
                    speed=30.0,
                    heading=90.0,
                    timestamp=timezone.now()
                )

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {routes_count} Bus Routes & {buses_count} Buses.'))
        self.stdout.write(self.style.SUCCESS(f'Total Bus Stops in DB: {BusStop.objects.count()}'))
