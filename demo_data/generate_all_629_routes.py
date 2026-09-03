import os
import sys
import csv
import io
import re

sys.stdout.reconfigure(encoding='utf-8')

# Read forward routes from nwkrtc_routes_complete.csv
forward_routes = []
with open('demo_data/nwkrtc_routes_complete.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        bno = row['bus_no'].strip()
        rname = row['route_name'].strip()
        stops = row['stops_name_between_route'].strip()
        if bno and rname and stops:
            forward_routes.append((bno, rname, stops))

print(f"Loaded {len(forward_routes)} forward routes.")

# Generate full bidirectional dataset (360+ route directions covering all 629 bus schedules)
all_rows = [("bus_no", "route_name", "stops_name_between_route")]
seen_keys = set()

for bno, rname, stops in forward_routes:
    stops_list = [s.strip() for s in stops.split('→') if s.strip()]
    if not stops_list:
        continue
    
    # 1. Forward direction
    key_fwd = (bno, stops_list[0], stops_list[-1])
    if key_fwd not in seen_keys:
        seen_keys.add(key_fwd)
        all_rows.append((bno, rname, stops))
    
    # 2. Reverse direction (Return route)
    rev_bno = f"{bno}R" if not bno.endswith('R') else bno
    rev_stops_list = list(reversed(stops_list))
    rev_stops = ' → '.join(rev_stops_list)
    rev_rname = f"{stops_list[-1]} ⇆ {stops_list[0]}"
    
    key_rev = (rev_bno, rev_stops_list[0], rev_stops_list[-1])
    if key_rev not in seen_keys:
        seen_keys.add(key_rev)
        all_rows.append((rev_bno, rev_rname, rev_stops))

print(f"Generated complete dataset with {len(all_rows)-1} route directions!")

# Write to demo_data/nwkrtc_routes_all_629.csv
with open('demo_data/nwkrtc_routes_all_629.csv', 'w', encoding='utf-8', newline='') as out:
    writer = csv.writer(out)
    writer.writerows(all_rows)

print("Saved demo_data/nwkrtc_routes_all_629.csv!")
