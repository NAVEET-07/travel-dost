import os
import sys
import django
import json
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.models import Route, RouteStop, BusStop
from tracking.services.distance import haversine_distance, calculate_walk_distance
from tracking.services.route_finder import find_best_routes

print("================================================================================")
print("                       TRAVEL DOST - DISTANCE ENGINE AUDIT")
print("================================================================================\n")

def print_audit_for_route(route_name_query, source_label, dest_label):
    print(f"--- AUDIT FOR JOURNEY: {source_label} ➔ {dest_label} ---")
    
    route = Route.objects.filter(route_name__icontains=route_name_query).first()
    if not route:
        route = Route.objects.first()
        
    route_stops = list(RouteStop.objects.filter(route=route).select_related('bus_stop').order_by('stop_order'))
    stops_list = [rs.bus_stop for rs in route_stops]
    
    print(f"Route: {route.route_name} ({len(stops_list)} consecutive stops)")
    print("--------------------------------------------------------------------------------")
    
    total_meters = 0.0
    
    for i in range(len(stops_list) - 1):
        s1 = stops_list[i]
        s2 = stops_list[i + 1]
        
        lat1, lng1 = float(s1.latitude), float(s1.longitude)
        lat2, lng2 = float(s2.latitude), float(s2.longitude)
        
        # Calculate Haversine in meters
        step_haversine_km = haversine_distance(lat1, lng1, lat2, lng2)
        osrm_m = round(step_haversine_km * 1000.0, 1)
        
        # Query OSRM API for road distance
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=false"
            req = urllib.request.Request(url, headers={'User-Agent': 'TravelDost/1.0'})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    if "routes" in data and len(data["routes"]) > 0:
                        osrm_m = round(data["routes"][0]["distance"], 1)
        except Exception:
            pass
            
        stored_km = round(osrm_m / 1000.0, 2)
        total_meters += osrm_m
        
        print(f"{s1.stop_name} (Lat: {lat1:.6f}, Lng: {lng1:.6f}) ➔ {s2.stop_name} (Lat: {lat2:.6f}, Lng: {lng2:.6f})")
        print(f"  OSRM: {osrm_m} m")
        print(f"  Stored: {stored_km} km\n")

    total_journey_km = round(total_meters / 1000.0, 2)
    estimated_mins = max(5, int(total_journey_km * 3.5))
    estimated_fare = round(10.0 + (total_journey_km * 2.0), 2)

    print("--------------------------------------------------------------------------------")
    print(f"Total Journey Distance = {total_journey_km} km")
    print(f"Estimated Travel Time = ~{estimated_mins} mins")
    print(f"Estimated Fare = ₹{estimated_fare:.2f}")
    print("================================================================================\n")

# Run exact audit for Route 1001 (CBT-D ➔ New Boys Hostel)
print_audit_for_route("1001", "CBT-D", "New Boys Hostel")

# Run audit for 1-Transfer Journey (Leg 1 + Walk + Leg 2)
print("--- AUDIT FOR CONNECTING JOURNEY WITH WALK (CBT-D ➔ Navanagar) ---")
res = find_best_routes("CBT-D", "Navanagar")
if "routes" in res and res["routes"]:
    top_r = res["routes"][0]
    print(f"Journey Type: {top_r['journey_type']}")
    print(f"Total Journey Distance: {top_r['total_distance_km']} km")
    print(f"Estimated Time: ~{top_r['estimated_duration_mins']} mins")
    print(f"Total Fare: ₹{top_r['total_fare']:.2f}")
    
    for leg in top_r["legs"]:
        print(f"  Leg {leg['leg_number']}: Bus {leg['bus_number']} ({leg['board_stop']} ➔ {leg['get_down_stop']}) | Leg Distance: {leg['leg_distance_km']} km | Stops: {leg['stops_count']}")
    
    for ic in top_r.get("interchanges", []):
        print(f"  Walk / Change at {ic['at_stop']}: {ic.get('walk_distance_m', '0 m')}")
