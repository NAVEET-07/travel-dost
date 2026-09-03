import os
import sys
import django
import time

sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_dost_backend.settings')
django.setup()

from tracking.services.route_finder import TransportGraph, resolve_bus_stop

graph = TransportGraph.get_graph()

def find_fast_multi_hop_routes(src_stop, dst_stop):
    src_canonical_ids = graph.get_equivalent_stop_ids(src_stop.id)
    dst_canonical_ids = graph.get_equivalent_stop_ids(dst_stop.id)

    # 1. Routes passing through Source
    src_routes_info = []
    for sid in src_canonical_ids:
        src_routes_info.extend(graph.stop_to_routes.get(sid, []))

    # 2. Routes passing through Destination
    dst_routes_info = []
    for sid in dst_canonical_ids:
        dst_routes_info.extend(graph.stop_to_routes.get(sid, []))

    # Downstream stops reachable from Source on Leg 1
    leg1_downstream = {} # stop_id -> (r1_id, s_phys_id, x1_phys_id, stops_cnt)
    for r1_id, s_order, s_dist in src_routes_info:
        seq1 = graph.route_seq[r1_id]
        s_phys_id = next(item[0] for item in seq1 if item[1] == s_order)
        for x1_sid, x1_order, x1_dist in seq1:
            if x1_order > s_order:
                if x1_sid not in leg1_downstream:
                    leg1_downstream[x1_sid] = (r1_id, s_phys_id, x1_sid, x1_order - s_order)

    # Upstream stops on Leg 3 that reach Destination
    leg3_upstream = {} # stop_id -> (r3_id, y3_phys_id, d_phys_id, stops_cnt)
    for r3_id, d_order, d_dist in dst_routes_info:
        seq3 = graph.route_seq[r3_id]
        d_phys_id = next(item[0] for item in seq3 if item[1] == d_order)
        for y3_sid, y3_order, y3_dist in seq3:
            if y3_order < d_order:
                if y3_sid not in leg3_upstream:
                    leg3_upstream[y3_sid] = (r3_id, y3_sid, d_phys_id, d_order - y3_order)

    found = []
    # Find middle routes R2 connecting X (from Leg 1) to Y (for Leg 3)
    for x_sid, (r1_id, s_phys_id, x1_phys_id, cnt1) in leg1_downstream.items():
        x_canon = graph.get_equivalent_stop_ids(x_sid)
        x_routes = []
        for cid in x_canon:
            x_routes.extend(graph.stop_to_routes.get(cid, []))
        
        for r2_id, x2_order, x2_dist in x_routes:
            if r2_id == r1_id:
                continue
            seq2 = graph.route_seq[r2_id]
            for y2_sid, y2_order, y2_dist in seq2:
                if y2_order > x2_order:
                    y_canon = graph.get_equivalent_stop_ids(y2_sid)
                    for ycid in y_canon:
                        if ycid in leg3_upstream:
                            r3_id, y3_phys_id, d_phys_id, cnt3 = leg3_upstream[ycid]
                            if r3_id != r2_id and r3_id != r1_id:
                                found.append({
                                    "r1": r1_id, "x": x_sid, "r2": r2_id, "y": y2_sid, "r3": r3_id,
                                    "s": s_phys_id, "d": d_phys_id,
                                    "tot_stops": cnt1 + (y2_order - x2_order) + cnt3
                                })
                                if len(found) >= 5:
                                    break
                    if len(found) >= 5:
                        break
            if len(found) >= 5:
                break
        if len(found) >= 5:
            break

    return found

s1, _ = resolve_bus_stop("Madihal")
s2, _ = resolve_bus_stop("Chabbi")

t0 = time.time()
multi = find_fast_multi_hop_routes(s1, s2)
t1 = time.time()

print(f"Fast Multi-hop Search executed in {round((t1-t0)*1000, 2)} ms!")
print(f"Found {len(multi)} multi-hop paths:")
for m in multi:
    r1 = graph.route_map[m['r1']].route_name
    r2 = graph.route_map[m['r2']].route_name
    r3 = graph.route_map[m['r3']].route_name
    x_name = graph.stop_map[m['x']].stop_name
    y_name = graph.stop_map[m['y']].stop_name
    print(f"  Path: {r1} ➔ (Change at {x_name}) ➔ {r2} ➔ (Change at {y_name}) ➔ {r3} (Total stops: {m['tot_stops']})")
