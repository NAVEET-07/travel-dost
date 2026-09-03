import os
import sys
import django
import time

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.models import BusStop, RouteStop, Route, Bus
from tracking.services.route_finder import clean_stop_name, normalize_text, resolve_bus_stop

all_stops = list(BusStop.objects.filter(is_active=True))

def get_canonical_stop_ids(stop_obj):
    if not stop_obj:
        return []
    base_name = normalize_text(clean_stop_name(stop_obj.stop_name))
    ids = set()
    for s in all_stops:
        c = normalize_text(clean_stop_name(s.stop_name))
        if c and (c == base_name or c.startswith(base_name) or base_name.startswith(c)):
            ids.add(s.id)
    ids.add(stop_obj.id)
    return list(ids)

test_stops = ["CBT-D", "Navanagar", "Railway Station", "KLE Technological University"]
for ts in test_stops:
    st, _ = resolve_bus_stop(ts)
    if st:
        c_ids = get_canonical_stop_ids(st)
        c_names = [s.stop_name for s in all_stops if s.id in c_ids]
        print(f"Stop '{ts}' => Base '{st.stop_name}' ({len(c_ids)} physical variants): {c_names[:5]}")
