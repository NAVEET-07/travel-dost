import os
import sys
import django
import time

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.services.route_finder import find_best_routes

t0 = time.time()
res = find_best_routes('Madihal', 'Chabbi')
t1 = time.time()

print(f"Madihal to Chabbi search executed in {round((t1-t0)*1000, 2)} ms")
print("Result keys:", list(res.keys()))
if "routes" in res:
    print("Found routes:", len(res["routes"]))
    for r in res["routes"]:
        print(f"  {r['journey_type']} ({r['transfers']} transfers): {r['route_name']}")
        for leg in r["legs"]:
            print(f"    Leg {leg['leg_number']}: Bus {leg['bus_number']} ({leg['board_stop']} ➔ {leg['get_down_stop']})")
