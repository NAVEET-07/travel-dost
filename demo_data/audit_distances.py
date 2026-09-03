import os
import sys
import django
import math
import json
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.models import BusStop, RouteStop, Route
from tracking.services.distance import haversine_distance

print("=== 1. AUDITING ALL BUS STOP GPS COORDINATES ===")
stops = list(BusStop.objects.filter(is_active=True))
print(f"Total Active Bus Stops: {len(stops)}")

invalid_coords = []
swapped_coords = []
out_of_bounds = []

for s in stops:
    lat = float(s.latitude)
    lng = float(s.longitude)
    
    # Check if lat/lng are 0 or null
    if lat == 0.0 or lng == 0.0:
        invalid_coords.append(s)
    # Check if lat/lng are swapped (lng is ~15 and lat is ~75)
    elif lat > 30.0 or lng < 30.0:
        swapped_coords.append(s)
    # Check Hubballi-Dharwad bounding box (Lat: 15.1..15.6, Lng: 74.8..75.3)
    elif not (15.1 <= lat <= 15.6 and 74.8 <= lng <= 75.3):
        out_of_bounds.append((s, lat, lng))

print(f"Invalid Coords (0.0, 0.0): {len(invalid_coords)}")
print(f"Swapped Coords (Lat > 30 or Lng < 30): {len(swapped_coords)}")
print(f"Out of Bounding Box Coords: {len(out_of_bounds)}")

if out_of_bounds:
    print("\nSample Out of Bounds Stops:")
    for s, lat, lng in out_of_bounds[:10]:
        print(f"  ID {s.id}: {s.stop_name} (Lat: {lat}, Lng: {lng})")

print("\n=== 2. AUDITING DISTANCE CALCULATION LOGIC & OSRM API ===")

def audit_journey_leg(route_id):
    route = Route.objects.filter(id=route_id).first()
    if not route:
        print(f"Route {route_id} not found.")
        return
    
    route_stops = RouteStop.objects.filter(route=route).select_related('bus_stop').order_by('stop_order')
    stops_list = [rs.bus_stop for rs in route_stops]
    
    print(f"\nAudit for {route.route_name} ({len(stops_list)} stops):")
    print("--------------------------------------------------------------------------------")
    
    total_meters_osrm = 0.0
    total_km_haversine = 0.0
    
    for i in range(len(stops_list) - 1):
        s1 = stops_list[i]
        s2 = stops_list[i + 1]
        
        lat1, lng1 = float(s1.latitude), float(s1.longitude)
        lat2, lng2 = float(s2.latitude), float(s2.longitude)
        
        # Calculate Haversine between consecutive pair
        step_haversine_km = haversine_distance(lat1, lng1, lat2, lng2)
        step_haversine_m = int(step_haversine_km * 1000)
        
        # Query OSRM for pair
        osrm_m = step_haversine_m
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=false"
            req = urllib.request.Request(url, headers={'User-Agent': 'TravelDost/1.0'})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    if "routes" in data and len(data["routes"]) > 0:
                        osrm_m = round(data["routes"][0]["distance"], 1)
        except Exception as e:
            pass
            
        stored_km = round(osrm_m / 1000.0, 2)
        total_meters_osrm += osrm_m
        total_km_haversine += step_haversine_km
        
        flag = " [ABNORMAL > 3km]" if stored_km > 3.0 else ""
        print(f"{s1.stop_name} (Lat: {lat1}, Lng: {lng1}) ➔ {s2.stop_name} (Lat: {lat2}, Lng: {lng2})")
        print(f"  OSRM: {osrm_m} m | Stored: {stored_km} km{flag}")
        
    total_stored_km = round(total_meters_osrm / 1000.0, 2)
    print("--------------------------------------------------------------------------------")
    print(f"Total Journey Distance = {total_stored_km} km (OSRM sum)")
    print(f"Total Haversine Distance = {round(total_km_haversine, 2)} km")

# Test for Route 1001 (Cbt-D ➔ New Boys Hostel)
route_1001 = Route.objects.filter(route_name__icontains="1001").first()
if route_1001:
    audit_journey_leg(route_1001.id)
else:
    audit_journey_leg(Route.objects.first().id)
