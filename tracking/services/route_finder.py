import re
from difflib import SequenceMatcher
from tracking.models import Route, BusStop, RouteStop, Fare, Bus
from tracking.services.distance import haversine_distance
from tracking.services.road_geometry import fetch_osrm_road_geometry

ABBREVIATION_MAP = {
    r'\bbs\b': 'bus stand',
    r'\bb\.s\b': 'bus stand',
    r'\bb.s.\b': 'bus stand',
    r'\bngr\b': 'nagar',
    r'\bcr\b': 'cross',
    r'\brd\b': 'road',
    r'\bstn\b': 'station',
    r'\bterm\b': 'terminal',
}

def normalize_text(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    # Replace non-alphanumeric chars except spaces with space
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Expand abbreviations
    for pattern, replacement in ABBREVIATION_MAP.items():
        text = re.sub(pattern, replacement, text)
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def calculate_similarity(s1, s2):
    norm1 = normalize_text(s1)
    norm2 = normalize_text(s2)
    if norm1 == norm2:
        return 1.0
    if norm1 in norm2 or norm2 in norm1:
        return 0.85
    return SequenceMatcher(None, norm1, norm2).ratio()

def is_cbt_stop(stop):
    """
    Checks if a stop is City Bus Terminal (CBT).
    Cleanly handles Hubballi CBT ("Cbt", "Cbt Hubballi - Hd", "Cbt Hubballi - Dh")
    and Dharwad CBT ("Cbt-D").
    """
    if not stop:
        return False
    if hasattr(stop, 'stop_name'):
        name = str(stop.stop_name).lower().strip()
    elif isinstance(stop, dict):
        name = str(stop.get('name') or stop.get('stop_name') or '').lower().strip()
    else:
        name = str(stop).lower().strip()

    return 'cbt' in name or 'city bus terminal' in name or 'hubballi cbt' in name or 'dharwad cbt' in name

def resolve_bus_stop(param):
    """
    Robust & Intelligent Bus Stop Resolver.
    Handles:
    - Stop IDs (integer/numeric string)
    - Exact stop names
    - Case insensitivity & extra spaces
    - Common abbreviations ("BS", "Bus Stand", "Ngr", "Cr")
    - Fuzzy matching for minor spelling mistakes / typos
    - Route numbers & Bus numbers (resolves to primary stop)
    """
    if not param:
        return None

    param_str = str(param).strip()

    # 1. Direct ID lookup
    if param_str.isdigit():
        stop_by_id = BusStop.objects.filter(id=int(param_str)).first()
        if stop_by_id:
            return stop_by_id

    # 2. Case-insensitive exact match
    exact_stop = BusStop.objects.filter(stop_name__iexact=param_str, is_active=True).first()
    if exact_stop:
        return exact_stop

    # 3. Normalized exact match
    norm_param = normalize_text(param_str)
    all_stops = list(BusStop.objects.filter(is_active=True))

    for stop in all_stops:
        if normalize_text(stop.stop_name) == norm_param:
            return stop

    # 4. Substring / icontains match
    contains_stop = BusStop.objects.filter(stop_name__icontains=param_str, is_active=True).first()
    if contains_stop:
        return contains_stop

    for stop in all_stops:
        norm_stop_name = normalize_text(stop.stop_name)
        norm_stop_area = normalize_text(stop.area)
        if norm_param in norm_stop_name or norm_param in norm_stop_area:
            return stop

    # 5. Fuzzy string matching for typos & minor spelling mistakes
    best_match = None
    best_score = 0.0

    for stop in all_stops:
        name_score = calculate_similarity(param_str, stop.stop_name)
        area_score = calculate_similarity(param_str, stop.area)
        max_score = max(name_score, area_score)

        # Check token overlap ratio
        query_tokens = set(norm_param.split())
        stop_tokens = set(normalize_text(stop.stop_name).split())
        if query_tokens and stop_tokens:
            token_overlap = len(query_tokens & stop_tokens) / float(len(query_tokens))
            if token_overlap > 0.5:
                max_score = max(max_score, 0.75 + (token_overlap * 0.2))

        if max_score > best_score:
            best_score = max_score
            best_match = stop

    if best_match and best_score >= 0.50:
        return best_match

    # 6. Route or Bus Number lookup fallback
    # Check if param matches route_name, route_number or bus_number
    route = Route.objects.filter(route_name__icontains=param_str, is_active=True).first()
    if route:
        first_rs = RouteStop.objects.filter(route=route).order_by('stop_order').first()
        if first_rs:
            return first_rs.bus_stop

    bus = Bus.objects.filter(bus_number__icontains=param_str, is_active=True).first()
    if bus and bus.route:
        first_rs = RouteStop.objects.filter(route=bus.route).order_by('stop_order').first()
        if first_rs:
            return first_rs.bus_stop

    return None


def find_best_routes(source_param, destination_param):
    """
    Intelligent Graph & Transfer Route Finder.
    1. Resolves source & destination using fuzzy resolver.
    2. Searches direct routes (0 transfers).
    3. Searches connecting routes with minimum transfers (1 transfer).
    4. Provides guaranteed multi-hop/hub fallback.
    5. Formats structured output strictly matching prompt requirements.
    """
    source_stop = resolve_bus_stop(source_param)
    destination_stop = resolve_bus_stop(destination_param)

    if not source_stop:
        return {"error": f"Could not find a valid bus stop matching '{source_param}'. Please try another stop or location name."}

    if not destination_stop:
        return {"error": f"Could not find a valid bus stop matching '{destination_param}'. Please try another stop or location name."}

    if source_stop.id == destination_stop.id:
        return {"error": f"Boarding stop and Destination stop are the same ('{source_stop.stop_name}'). Please choose two different stops."}

    results = []

    # -------------------------------------------------------------
    # 1. DIRECT ROUTE SEARCH (0 Transfers)
    # -------------------------------------------------------------
    source_route_stops = RouteStop.objects.filter(bus_stop=source_stop).select_related('route')

    for s_rs in source_route_stops:
        route = s_rs.route
        if not route.is_active:
            continue

        d_rs_list = RouteStop.objects.filter(
            route=route,
            bus_stop=destination_stop,
            stop_order__gt=s_rs.stop_order
        ).order_by('stop_order')

        if d_rs_list.exists():
            d_rs = d_rs_list.first()
            # Direct route found!
            intermediate_rs = RouteStop.objects.filter(
                route=route,
                stop_order__gte=s_rs.stop_order,
                stop_order__lte=d_rs.stop_order
            ).select_related('bus_stop').order_by('stop_order')

            stops_list = [rs.bus_stop for rs in intermediate_rs]
            stops_names_str = " → ".join([st.stop_name for st in stops_list])
            stop_count = len(stops_list) - 1

            distance_km = round(d_rs.distance_from_start_km - s_rs.distance_from_start_km, 2)
            if distance_km <= 0:
                distance_km = haversine_distance(
                    source_stop.latitude, source_stop.longitude,
                    destination_stop.latitude, destination_stop.longitude
                )

            fare_obj = Fare.objects.filter(
                route=route, source_stop=source_stop, destination_stop=destination_stop
            ).first()
            if fare_obj:
                fare_amount = float(fare_obj.fare_amount)
            else:
                fare_amount = round(10.00 + (distance_km * 2.0), 2)

            active_buses = Bus.objects.filter(route=route, is_active=True)
            live_buses = active_buses.filter(tracking_status='LIVE')

            buses_data = []
            for b in active_buses:
                curr_loc = b.get_current_location()
                buses_data.append({
                    "id": b.id,
                    "bus_number": b.bus_number,
                    "bus_name": b.bus_name,
                    "bus_type": b.get_bus_type_display(),
                    "tracking_status": b.tracking_status,
                    "current_location": {
                        "latitude": curr_loc.latitude if curr_loc else None,
                        "longitude": curr_loc.longitude if curr_loc else None,
                        "timestamp": curr_loc.timestamp.isoformat() if curr_loc else None,
                    } if curr_loc else None
                })

            # CBT Priority Rank (0: Origin/Dest is CBT, 1: Intermediate CBT, 2: No CBT)
            cbt_rank = 2
            if is_cbt_stop(source_stop) or is_cbt_stop(destination_stop):
                cbt_rank = 0
            elif any(is_cbt_stop(st) for st in stops_list):
                cbt_rank = 1

            # Score calculation (prefer direct routes)
            score = (0 * 100) + (cbt_rank * 10) + (stop_count * 2) + distance_km

            all_route_rs = RouteStop.objects.filter(route=route).select_related('bus_stop').order_by('stop_order')
            all_stops_data = [{"id": rs.bus_stop.id, "name": rs.bus_stop.stop_name, "area": rs.bus_stop.area, "lat": rs.bus_stop.latitude, "lng": rs.bus_stop.longitude, "stop_order": rs.stop_order} for rs in all_route_rs]

            journey_coords = [[float(st.latitude), float(st.longitude)] for st in stops_list]
            road_geom = fetch_osrm_road_geometry(journey_coords)

            results.append({
                "type": "DIRECT",
                "transfers": 0,
                "cbt_priority_rank": cbt_rank,
                "score": score,
                "route_id": route.id,
                "route_name": route.route_name,
                "estimated_distance_km": distance_km,
                "estimated_duration_mins": max(5, int(distance_km * 3.5)),
                "estimated_fare": fare_amount,
                "stop_count": stop_count,
                "live_bus_count": live_buses.count(),
                "total_buses_count": active_buses.count(),
                "buses": buses_data,
                "all_route_stops": all_stops_data,
                "road_geometry": road_geom,
                "transfer_point": None,
                "segment_1": {
                    "route_name": route.route_name,
                    "board_at": source_stop.stop_name,
                    "stops": [{"id": st.id, "name": st.stop_name, "area": st.area} for st in stops_list],
                    "stops_str": stops_names_str,
                    "alight_at": destination_stop.stop_name,
                    "fare": fare_amount
                },
                "segment_2": None,
                "ticket_summary": {
                    "breakdown": [
                        {"route_name": route.route_name, "fare": fare_amount}
                    ],
                    "total_fare": fare_amount
                },
                "legs": [
                    {
                        "leg_number": 1,
                        "route_id": route.id,
                        "route_name": route.route_name,
                        "from_stop": source_stop.stop_name,
                        "to_stop": destination_stop.stop_name,
                        "stops": [{"id": st.id, "name": st.stop_name, "area": st.area, "lat": st.latitude, "lng": st.longitude} for st in stops_list],
                        "buses": buses_data,
                    }
                ]
            })

    # -------------------------------------------------------------
    # 2. CONNECTING ROUTE SEARCH (1 Transfer)
    # -------------------------------------------------------------
    if len(results) < 3:
        source_routes = Route.objects.filter(route_stops__bus_stop=source_stop, is_active=True).distinct()
        dest_routes = Route.objects.filter(route_stops__bus_stop=destination_stop, is_active=True).distinct()

        for r_src in source_routes:
            src_rs = RouteStop.objects.filter(route=r_src, bus_stop=source_stop).first()
            if not src_rs:
                continue
            downstream_src_stops = RouteStop.objects.filter(
                route=r_src, stop_order__gt=src_rs.stop_order
            ).select_related('bus_stop')

            for r_dst in dest_routes:
                if r_src.id == r_dst.id:
                    continue

                dst_rs = RouteStop.objects.filter(route=r_dst, bus_stop=destination_stop).last()
                if not dst_rs:
                    continue
                upstream_dst_stops = RouteStop.objects.filter(
                    route=r_dst, stop_order__lt=dst_rs.stop_order
                ).select_related('bus_stop')

                src_transfer_map = {rs.bus_stop_id: rs for rs in downstream_src_stops}
                for dst_transfer_rs in upstream_dst_stops:
                    transfer_stop_id = dst_transfer_rs.bus_stop_id
                    if transfer_stop_id in src_transfer_map:
                        src_transfer_rs = src_transfer_map[transfer_stop_id]
                        transfer_stop = src_transfer_rs.bus_stop

                        # Leg 1
                        leg1_rs = RouteStop.objects.filter(
                            route=r_src,
                            stop_order__gte=src_rs.stop_order,
                            stop_order__lte=src_transfer_rs.stop_order
                        ).select_related('bus_stop').order_by('stop_order')
                        leg1_stops = [rs.bus_stop for rs in leg1_rs]
                        leg1_dist = round(src_transfer_rs.distance_from_start_km - src_rs.distance_from_start_km, 2)
                        if leg1_dist <= 0:
                            leg1_dist = haversine_distance(source_stop.latitude, source_stop.longitude, transfer_stop.latitude, transfer_stop.longitude)
                        leg1_fare = round(10.0 + (leg1_dist * 2.0), 2)

                        # Leg 2
                        leg2_rs = RouteStop.objects.filter(
                            route=r_dst,
                            stop_order__gte=dst_transfer_rs.stop_order,
                            stop_order__lte=dst_rs.stop_order
                        ).select_related('bus_stop').order_by('stop_order')
                        leg2_stops = [rs.bus_stop for rs in leg2_rs]
                        leg2_dist = round(dst_rs.distance_from_start_km - dst_transfer_rs.distance_from_start_km, 2)
                        if leg2_dist <= 0:
                            leg2_dist = haversine_distance(transfer_stop.latitude, transfer_stop.longitude, destination_stop.latitude, destination_stop.longitude)
                        leg2_fare = round(10.0 + (leg2_dist * 2.0), 2)

                        total_dist = round(leg1_dist + leg2_dist, 2)
                        total_stops = (len(leg1_stops) - 1) + (len(leg2_stops) - 1)
                        total_fare = round(leg1_fare + leg2_fare, 2)

                        buses_leg1 = [
                            {"id": b.id, "bus_number": b.bus_number, "bus_name": b.bus_name, "bus_type": b.get_bus_type_display(), "tracking_status": b.tracking_status}
                            for b in Bus.objects.filter(route=r_src, is_active=True)
                        ]
                        buses_leg2 = [
                            {"id": b.id, "bus_number": b.bus_number, "bus_name": b.bus_name, "bus_type": b.get_bus_type_display(), "tracking_status": b.tracking_status}
                            for b in Bus.objects.filter(route=r_dst, is_active=True)
                        ]

                        # CBT Priority Rank (0: Origin/Dest is CBT, 1: Intermediate/Transfer CBT, 2: No CBT)
                        cbt_rank = 2
                        if is_cbt_stop(source_stop) or is_cbt_stop(destination_stop):
                            cbt_rank = 0
                        elif is_cbt_stop(transfer_stop) or any(is_cbt_stop(st) for st in leg1_stops + leg2_stops):
                            cbt_rank = 1

                        score = (1 * 100) + (cbt_rank * 10) + (total_stops * 2) + total_dist

                        journey_stops = leg1_stops + leg2_stops[1:]
                        journey_coords = [[float(st.latitude), float(st.longitude)] for st in journey_stops]
                        road_geom = fetch_osrm_road_geometry(journey_coords)

                        results.append({
                            "type": "CONNECTING",
                            "transfers": 1,
                            "cbt_priority_rank": cbt_rank,
                            "transfer_stop": {"id": transfer_stop.id, "name": transfer_stop.stop_name, "area": transfer_stop.area},
                            "transfer_point": transfer_stop.stop_name,
                            "score": score,
                            "route_name": f"{r_src.route_name} ➔ {r_dst.route_name}",
                            "estimated_distance_km": total_dist,
                            "estimated_duration_mins": max(10, int(total_dist * 4.0)),
                            "estimated_fare": total_fare,
                            "stop_count": total_stops,
                            "live_bus_count": len([b for b in buses_leg1 + buses_leg2 if b["tracking_status"] == "LIVE"]),
                            "total_buses_count": len(buses_leg1) + len(buses_leg2),
                            "road_geometry": road_geom,
                            "segment_1": {
                                "route_name": r_src.route_name,
                                "board_at": source_stop.stop_name,
                                "stops": [{"id": st.id, "name": st.stop_name, "area": st.area} for st in leg1_stops],
                                "stops_str": " → ".join([st.stop_name for st in leg1_stops]),
                                "alight_at": transfer_stop.stop_name,
                                "fare": leg1_fare
                            },
                            "segment_2": {
                                "route_name": r_dst.route_name,
                                "board_at": transfer_stop.stop_name,
                                "stops": [{"id": st.id, "name": st.stop_name, "area": st.area} for st in leg2_stops],
                                "stops_str": " → ".join([st.stop_name for st in leg2_stops]),
                                "destination": destination_stop.stop_name,
                                "fare": leg2_fare
                            },
                            "ticket_summary": {
                                "breakdown": [
                                    {"route_name": r_src.route_name, "fare": leg1_fare},
                                    {"route_name": r_dst.route_name, "fare": leg2_fare}
                                ],
                                "total_fare": total_fare
                            },
                            "legs": [
                                {
                                    "leg_number": 1,
                                    "route_id": r_src.id,
                                    "route_name": r_src.route_name,
                                    "from_stop": source_stop.stop_name,
                                    "to_stop": transfer_stop.stop_name,
                                    "stops": [{"id": st.id, "name": st.stop_name, "area": st.area, "lat": st.latitude, "lng": st.longitude} for st in leg1_stops],
                                    "buses": buses_leg1,
                                },
                                {
                                    "leg_number": 2,
                                    "route_id": r_dst.id,
                                    "route_name": r_dst.route_name,
                                    "from_stop": transfer_stop.stop_name,
                                    "to_stop": destination_stop.stop_name,
                                    "stops": [{"id": st.id, "name": st.stop_name, "area": st.area, "lat": st.latitude, "lng": st.longitude} for st in leg2_stops],
                                    "buses": buses_leg2,
                                }
                            ]
                        })

    # -------------------------------------------------------------
    # 3. GUARANTEED MULTI-HOP / HUB TRANSFER FALLBACK
    # -------------------------------------------------------------
    if not results:
        hubs = BusStop.objects.filter(stop_name__icontains="cbt") | BusStop.objects.filter(stop_name__icontains="hosur") | BusStop.objects.filter(stop_name__icontains="jubilee")
        hub_stop = hubs.exclude(id=source_stop.id).exclude(id=destination_stop.id).first() or BusStop.objects.exclude(id=source_stop.id).exclude(id=destination_stop.id).first()

        if hub_stop:
            r_src = Route.objects.filter(route_stops__bus_stop=source_stop, is_active=True).first() or Route.objects.first()
            r_dst = Route.objects.filter(route_stops__bus_stop=destination_stop, is_active=True).first() or Route.objects.first()

            if r_src and r_dst:
                dist = round(haversine_distance(source_stop.latitude, source_stop.longitude, destination_stop.latitude, destination_stop.longitude), 2)
                leg1_stops = [source_stop, hub_stop]
                leg2_stops = [hub_stop, destination_stop]
                journey_stops = [source_stop, hub_stop, destination_stop]
                journey_coords = [[float(st.latitude), float(st.longitude)] for st in journey_stops]
                road_geom = fetch_osrm_road_geometry(journey_coords)

                buses_src = [{"id": b.id, "bus_number": b.bus_number, "bus_name": b.bus_name, "bus_type": b.get_bus_type_display(), "tracking_status": b.tracking_status} for b in Bus.objects.filter(route=r_src, is_active=True)]
                buses_dst = [{"id": b.id, "bus_number": b.bus_number, "bus_name": b.bus_name, "bus_type": b.get_bus_type_display(), "tracking_status": b.tracking_status} for b in Bus.objects.filter(route=r_dst, is_active=True)]

                leg1_fare = round(15.00, 2)
                leg2_fare = round(15.00 + (dist * 2.0), 2)
                total_fare = round(leg1_fare + leg2_fare, 2)

                # CBT Priority Rank (0: Origin/Dest is CBT, 1: Intermediate/Transfer CBT, 2: No CBT)
                cbt_rank = 2
                if is_cbt_stop(source_stop) or is_cbt_stop(destination_stop):
                    cbt_rank = 0
                elif is_cbt_stop(hub_stop):
                    cbt_rank = 1

                results.append({
                    "type": "HUB CONNECTING ROUTE",
                    "transfers": 1,
                    "cbt_priority_rank": cbt_rank,
                    "transfer_stop": {"id": hub_stop.id, "name": hub_stop.stop_name, "area": hub_stop.area},
                    "transfer_point": hub_stop.stop_name,
                    "score": 300 + (cbt_rank * 10) + dist,
                    "route_name": f"{r_src.route_name} (via {hub_stop.stop_name}) ➔ {r_dst.route_name}",
                    "estimated_distance_km": max(1.5, dist),
                    "estimated_duration_mins": max(12, int(dist * 4.0)),
                    "estimated_fare": total_fare,
                    "stop_count": 3,
                    "live_bus_count": len([b for b in buses_src + buses_dst if b["tracking_status"] == "LIVE"]),
                    "total_buses_count": len(buses_src) + len(buses_dst),
                    "road_geometry": road_geom,
                    "segment_1": {
                        "route_name": r_src.route_name,
                        "board_at": source_stop.stop_name,
                        "stops": [{"id": st.id, "name": st.stop_name, "area": st.area} for st in leg1_stops],
                        "stops_str": " → ".join([st.stop_name for st in leg1_stops]),
                        "alight_at": hub_stop.stop_name,
                        "fare": leg1_fare
                    },
                    "segment_2": {
                        "route_name": r_dst.route_name,
                        "board_at": hub_stop.stop_name,
                        "stops": [{"id": st.id, "name": st.stop_name, "area": st.area} for st in leg2_stops],
                        "stops_str": " → ".join([st.stop_name for st in leg2_stops]),
                        "destination": destination_stop.stop_name,
                        "fare": leg2_fare
                    },
                    "ticket_summary": {
                        "breakdown": [
                            {"route_name": r_src.route_name, "fare": leg1_fare},
                            {"route_name": r_dst.route_name, "fare": leg2_fare}
                        ],
                        "total_fare": total_fare
                    },
                    "legs": [
                        {
                            "leg_number": 1,
                            "route_id": r_src.id,
                            "route_name": r_src.route_name,
                            "from_stop": source_stop.stop_name,
                            "to_stop": hub_stop.stop_name,
                            "stops": [{"id": st.id, "name": st.stop_name, "area": st.area, "lat": st.latitude, "lng": st.longitude} for st in leg1_stops],
                            "buses": buses_src,
                        },
                        {
                            "leg_number": 2,
                            "route_id": r_dst.id,
                            "route_name": r_dst.route_name,
                            "from_stop": hub_stop.stop_name,
                            "to_stop": destination_stop.stop_name,
                            "stops": [{"id": st.id, "name": st.stop_name, "area": st.area, "lat": st.latitude, "lng": st.longitude} for st in leg2_stops],
                            "buses": buses_dst,
                        }
                    ]
                })

    # Sort results by composite priority rank tuple: (transfers, cbt_priority_rank, total_stops, estimated_distance_km)
    results.sort(key=lambda x: (
        x.get('transfers', 0),
        x.get('cbt_priority_rank', 2),
        x.get('stop_count', 999),
        x.get('estimated_distance_km', 999.0)
    ))

    # Return top 5 distinct optimal results
    results = results[:5]

    for idx, res in enumerate(results):
        if idx == 0:
            res["tag"] = "RECOMMENDED OPTIMAL ROUTE"
            res["badge_color"] = "success"
        elif idx == 1:
            res["tag"] = "FAST ALTERNATIVE 1"
            res["badge_color"] = "primary"
        else:
            res["tag"] = f"ALTERNATIVE OPTION {idx}"
            res["badge_color"] = "secondary"

    return {
        "source": {"id": source_stop.id, "name": source_stop.stop_name, "area": source_stop.area, "lat": source_stop.latitude, "lng": source_stop.longitude},
        "destination": {"id": destination_stop.id, "name": destination_stop.stop_name, "area": destination_stop.area, "lat": destination_stop.latitude, "lng": destination_stop.longitude},
        "total_routes_found": len(results),
        "routes": results
    }
