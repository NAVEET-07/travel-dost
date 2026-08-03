from tracking.models import Route, BusStop, RouteStop, Fare, Bus
from tracking.services.distance import haversine_distance


def find_best_routes(source_stop_id, destination_stop_id):
    """
    Intelligent route finder for Travel Dost.
    Finds direct routes and 1-transfer connecting routes between source and destination stops.
    Returns ranked route options with detailed leg breakdowns, stop lists, fares, and live bus availability.
    """
    try:
        source_stop = BusStop.objects.get(id=source_stop_id)
        destination_stop = BusStop.objects.get(id=destination_stop_id)
    except BusStop.DoesNotExist:
        return {"error": "Invalid source or destination stop specified."}

    if source_stop_id == destination_stop_id:
        return {"error": "Source and destination stops cannot be the same."}

    results = []

    # -------------------------------------------------------------
    # 1. DIRECT ROUTE SEARCH
    # -------------------------------------------------------------
    # Find all RouteStops for source_stop
    source_route_stops = RouteStop.objects.filter(bus_stop=source_stop).select_related('route')

    for s_rs in source_route_stops:
        route = s_rs.route
        if not route.is_active:
            continue

        # Check if destination_stop exists on the same route AFTER source_stop
        try:
            d_rs = RouteStop.objects.get(route=route, bus_stop=destination_stop)
            if d_rs.stop_order > s_rs.stop_order:
                # Direct route found!
                intermediate_rs = RouteStop.objects.filter(
                    route=route,
                    stop_order__gte=s_rs.stop_order,
                    stop_order__lte=d_rs.stop_order
                ).select_related('bus_stop').order_by('stop_order')

                stops_list = [rs.bus_stop for rs in intermediate_rs]
                stop_count = len(stops_list) - 1
                distance_km = round(d_rs.distance_from_start_km - s_rs.distance_from_start_km, 2)
                if distance_km <= 0:
                    distance_km = haversine_distance(
                        source_stop.latitude, source_stop.longitude,
                        destination_stop.latitude, destination_stop.longitude
                    )

                # Fare estimation
                fare_obj = Fare.objects.filter(
                    route=route, source_stop=source_stop, destination_stop=destination_stop
                ).first()
                if fare_obj:
                    fare_amount = float(fare_obj.fare_amount)
                else:
                    # Default estimated fare formula: Base ₹10 + ₹2 per KM
                    fare_amount = round(10.00 + (distance_km * 2.0), 2)

                # Check for active buses on this route
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

                # Score: lower is better (0 transfers = 0 penalty)
                score = (0 * 100) + (stop_count * 2) + distance_km

                results.append({
                    "type": "DIRECT",
                    "transfers": 0,
                    "score": score,
                    "route_name": route.route_name,
                    "estimated_distance_km": distance_km,
                    "estimated_duration_mins": max(5, int(distance_km * 3.5)),
                    "estimated_fare": fare_amount,
                    "stop_count": stop_count,
                    "live_bus_count": live_buses.count(),
                    "total_buses_count": active_buses.count(),
                    "buses": buses_data,
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
        except RouteStop.DoesNotExist:
            continue

    # -------------------------------------------------------------
    # 2. CONNECTING ROUTE SEARCH (1 Transfer)
    # -------------------------------------------------------------
    if len(results) < 3:
        # Find all routes leaving source_stop
        source_routes = Route.objects.filter(route_stops__bus_stop=source_stop, is_active=True).distinct()
        # Find all routes reaching destination_stop
        dest_routes = Route.objects.filter(route_stops__bus_stop=destination_stop, is_active=True).distinct()

        for r_src in source_routes:
            src_rs = RouteStop.objects.get(route=r_src, bus_stop=source_stop)
            # Stops after source_stop on r_src
            downstream_src_stops = RouteStop.objects.filter(
                route=r_src, stop_order__gt=src_rs.stop_order
            ).select_related('bus_stop')

            for r_dst in dest_routes:
                if r_src.id == r_dst.id:
                    continue  # Already checked in direct

                dst_rs = RouteStop.objects.get(route=r_dst, bus_stop=destination_stop)
                # Stops before destination_stop on r_dst
                upstream_dst_stops = RouteStop.objects.filter(
                    route=r_dst, stop_order__lt=dst_rs.stop_order
                ).select_related('bus_stop')

                # Find common transfer stop
                src_transfer_map = {rs.bus_stop_id: rs for rs in downstream_src_stops}
                for dst_transfer_rs in upstream_dst_stops:
                    transfer_stop_id = dst_transfer_rs.bus_stop_id
                    if transfer_stop_id in src_transfer_map:
                        src_transfer_rs = src_transfer_map[transfer_stop_id]
                        transfer_stop = src_transfer_rs.bus_stop

                        # Leg 1: Source to Transfer on r_src
                        leg1_stops_rs = RouteStop.objects.filter(
                            route=r_src,
                            stop_order__gte=src_rs.stop_order,
                            stop_order__lte=src_transfer_rs.stop_order
                        ).select_related('bus_stop').order_by('stop_order')
                        leg1_stops = [rs.bus_stop for rs in leg1_stops_rs]
                        leg1_dist = round(src_transfer_rs.distance_from_start_km - src_rs.distance_from_start_km, 2)
                        if leg1_dist <= 0:
                            leg1_dist = haversine_distance(source_stop.latitude, source_stop.longitude, transfer_stop.latitude, transfer_stop.longitude)

                        # Leg 2: Transfer to Destination on r_dst
                        leg2_stops_rs = RouteStop.objects.filter(
                            route=r_dst,
                            stop_order__gte=dst_transfer_rs.stop_order,
                            stop_order__lte=dst_rs.stop_order
                        ).select_related('bus_stop').order_by('stop_order')
                        leg2_stops = [rs.bus_stop for rs in leg2_stops_rs]
                        leg2_dist = round(dst_rs.distance_from_start_km - dst_transfer_rs.distance_from_start_km, 2)
                        if leg2_dist <= 0:
                            leg2_dist = haversine_distance(transfer_stop.latitude, transfer_stop.longitude, destination_stop.latitude, destination_stop.longitude)

                        total_dist = round(leg1_dist + leg2_dist, 2)
                        total_stops = (len(leg1_stops) - 1) + (len(leg2_stops) - 1)
                        total_fare = round(10.0 + (total_dist * 2.0), 2)

                        buses_leg1 = [
                            {"id": b.id, "bus_number": b.bus_number, "bus_name": b.bus_name, "bus_type": b.get_bus_type_display(), "tracking_status": b.tracking_status}
                            for b in Bus.objects.filter(route=r_src, is_active=True)
                        ]
                        buses_leg2 = [
                            {"id": b.id, "bus_number": b.bus_number, "bus_name": b.bus_name, "bus_type": b.get_bus_type_display(), "tracking_status": b.tracking_status}
                            for b in Bus.objects.filter(route=r_dst, is_active=True)
                        ]

                        score = (1 * 100) + (total_stops * 2) + total_dist

                        results.append({
                            "type": "CONNECTING",
                            "transfers": 1,
                            "transfer_stop": {"id": transfer_stop.id, "name": transfer_stop.stop_name, "area": transfer_stop.area},
                            "score": score,
                            "route_name": f"{r_src.route_name} ➔ {r_dst.route_name}",
                            "estimated_distance_km": total_dist,
                            "estimated_duration_mins": max(10, int(total_dist * 4.0)),
                            "estimated_fare": total_fare,
                            "stop_count": total_stops,
                            "live_bus_count": len([b for b in buses_leg1 + buses_leg2 if b["tracking_status"] == "LIVE"]),
                            "total_buses_count": len(buses_leg1) + len(buses_leg2),
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

    # Sort results by score (lower score = best route recommendation)
    results.sort(key=lambda x: x['score'])

    # Add tag/badge (Recommended, Fast Alternative, etc.)
    for idx, res in enumerate(results):
        if idx == 0:
            res["tag"] = "RECOMMENDED BEST ROUTE"
            res["badge_color"] = "success"
        elif idx == 1:
            res["tag"] = "ALTERNATIVE OPTION 1"
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
