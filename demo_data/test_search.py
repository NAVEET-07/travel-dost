import os
import sys
import django
import time

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.services.route_finder import resolve_bus_stop, find_best_routes
from tracking.models import BusStop

print("=== TESTING BUS STOP RESOLVER ===")
test_inputs = [
    "cbt",
    "CBT-D",
    "kle technological university",
    "railway station",
    "unkal",
    "navanagar",
    "nonexistent_stop_name_123"
]

for inp in test_inputs:
    stop_obj, suggs = resolve_bus_stop(inp)
    print(f"Input '{inp}' => Resolved: {stop_obj.stop_name if stop_obj else 'NONE'} (Suggestions: {len(suggs)})")

print("\n=== TESTING ROUTE SEARCH ENGINE ===")
search_pairs = [
    ("CBT Hubballi", "Dharwad CBT"),
    ("KLE Technological University", "Railway Station"),
    ("CBT-D", "Navanagar"),
    ("Betdur", "Hosur Terminal"),
    ("Nonexistent Stop A", "Nonexistent Stop B")
]

for src, dst in search_pairs:
    t0 = time.time()
    res = find_best_routes(src, dst)
    t1 = time.time()
    duration_ms = round((t1 - t0) * 1000, 2)
    print(f"\nSearch: '{src}' ➔ '{dst}' ({duration_ms} ms)")
    if "error" in res:
        print("  Error:", res["error"])
        if "suggestions" in res:
            print("  Suggestions:", [s["name"] for s in res["suggestions"]])
    else:
        print(f"  Total Journeys Found: {res['total_routes_found']}")
        for idx, r in enumerate(res['routes'][:2]):
            print(f"  Option #{idx+1} ({r['tag']}): {r['journey_type']} ({r['transfers']} transfers, {r['total_stops']} stops, {r['total_distance_km']} km)")
            for leg in r['legs']:
                print(f"    Leg {leg['leg_number']}: Bus {leg.get('bus_number', 'N/A')} on {leg['route_name']} ({leg['board_stop']} ➔ {leg['get_down_stop']}, {leg['stops_count']} stops)")
