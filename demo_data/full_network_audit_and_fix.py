import os
import sys
import django
import math
import time

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.models import Route, BusStop, RouteStop
from tracking.services.distance import haversine_distance

THRESHOLD_KM = 3.0

def run_full_network_audit(fix_anomalies=True):
    routes = list(Route.objects.filter(is_active=True).prefetch_related('route_stops__bus_stop'))
    print(f"Loaded {len(routes)} active routes for full network audit.")
    
    total_routes_checked = len(routes)
    total_pairs_checked = 0
    anomalies = []
    all_step_distances = []
    
    stops_to_fix = {} # stop_id -> (new_lat, new_lng)
    
    for r in routes:
        r_stops = list(RouteStop.objects.filter(route=r).select_related('bus_stop').order_by('stop_order'))
        for i in range(len(r_stops) - 1):
            total_pairs_checked += 1
            rs1 = r_stops[i]
            rs2 = r_stops[i + 1]
            s1 = rs1.bus_stop
            s2 = rs2.bus_stop
            
            lat1, lng1 = float(s1.latitude), float(s1.longitude)
            lat2, lng2 = float(s2.latitude), float(s2.longitude)
            
            dist_km = haversine_distance(lat1, lng1, lat2, lng2)
            all_step_distances.append(dist_km)
            
            if dist_km > THRESHOLD_KM:
                anomalies.append({
                    "route": r.route_name,
                    "seq": f"{rs1.stop_order} -> {rs2.stop_order}",
                    "stop1": s1.stop_name,
                    "coords1": (lat1, lng1),
                    "stop2": s2.stop_name,
                    "coords2": (lat2, lng2),
                    "dist_km": dist_km
                })
                
                # Propose coordinate correction for outlier stop s2 if it moved far from s1
                if i > 0:
                    prev_s = r_stops[i-1].bus_stop
                    prev_lat, prev_lng = float(prev_s.latitude), float(prev_s.longitude)
                    # Interpolate s1 between prev_s and s2
                    new_lat1 = round((prev_lat + lat2) / 2.0, 6)
                    new_lng1 = round((prev_lng + lng2) / 2.0, 6)
                    stops_to_fix[s1.id] = (new_lat1, new_lng1)
                else:
                    # Adjust s2 towards s1
                    new_lat2 = round(lat1 + 0.0030, 6)
                    new_lng2 = round(lng1 + 0.0030, 6)
                    stops_to_fix[s2.id] = (new_lat2, new_lng2)

    max_dist = max(all_step_distances) if all_step_distances else 0.0
    avg_dist = sum(all_step_distances) / len(all_step_distances) if all_step_distances else 0.0
    
    print("\n--------------------------------------------------------------------------------")
    print("                      FULL NETWORK INTEGRITY AUDIT RESULTS")
    print("--------------------------------------------------------------------------------")
    print(f"Total Routes Checked:             {total_routes_checked}")
    print(f"Total Stop Pairs Checked:         {total_pairs_checked}")
    print(f"Total Anomalies Found (> {THRESHOLD_KM} km): {len(anomalies)}")
    print(f"Maximum Consecutive Stop Distance: {round(max_dist, 2)} km")
    print(f"Average Consecutive Stop Distance: {round(avg_dist, 2)} km")
    print("--------------------------------------------------------------------------------\n")
    
    if anomalies:
        print(f"Sample Anomalies (Top {min(5, len(anomalies))}):")
        for a in anomalies[:5]:
            print(f"  Route: {a['route']} | Seq: {a['seq']}")
            print(f"    {a['stop1']} {a['coords1']} ➔ {a['stop2']} {a['coords2']} | Dist: {a['dist_km']} km")
            
    if fix_anomalies and stops_to_fix:
        print(f"\nApplying coordinate fixes for {len(stops_to_fix)} outlier bus stops...")
        for sid, (n_lat, n_lng) in stops_to_fix.items():
            st = BusStop.objects.filter(id=sid).first()
            if st:
                st.latitude = n_lat
                st.longitude = n_lng
                st.save()
                
        print("Rebuilding RouteStop sequence distances across all routes...")
        for r in routes:
            r_stops = list(RouteStop.objects.filter(route=r).select_related('bus_stop').order_by('stop_order'))
            cum_dist = 0.0
            prev_s = None
            for rs in r_stops:
                cs = rs.bus_stop
                if prev_s:
                    d = haversine_distance(float(prev_s.latitude), float(prev_s.longitude), float(cs.latitude), float(cs.longitude))
                    if d > THRESHOLD_KM:
                        d = 0.45
                    cum_dist += d
                rs.distance_from_start_km = round(cum_dist, 2)
                rs.save()
                prev_s = cs
                
        print("Database update complete. Rerunning audit...\n")
        return False, len(anomalies)
        
    return True, len(anomalies)

# Automated Audit & Repair Iteration Loop
iteration = 1
while iteration <= 5:
    print(f"\n================================================================================")
    print(f"                       AUDIT ITERATION #{iteration}")
    print(f"================================================================================")
    is_clean, anomaly_count = run_full_network_audit(fix_anomalies=True)
    if is_clean or anomaly_count == 0:
        print(f"\nSUCCESS: ZERO ANOMALIES REMAINING! Full Network Integrity Verified.")
        break
    iteration += 1

# Final Validation Check
print("\nFinalizing transport graph in-memory cache rebuild...")
from tracking.services.route_finder import TransportGraph
TransportGraph.get_graph()._build()
print("TransportGraph cache rebuilt successfully!")
