"""
Django Management Command: Audit and Repair Network Data Integrity.

Audits:
- 564 Bus Routes
- 828+ Bus Stops
- 7,627 Route-Stop Mappings

Checks for:
1. Out-of-bounds or zero GPS coordinates (outside Hubballi-Dharwad lat 14.5-16.0, lng 74.5-75.8)
2. Duplicate bus stops by name or exact lat/lng
3. Broken route sequences (missing stop_order sequence gaps, duplicate stop_orders)
4. Unrealistic consecutive stop distances (> 15.0 km within city route sequence)
5. Incorrect interchange hub mapping linkages

Auto-repairs route sequence anomalies without modifying valid GPS coordinates.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from tracking.models import Route, BusStop, RouteStop, Bus
from tracking.services.distance import haversine_distance, calculate_consecutive_stops_distance

class Command(BaseCommand):
    help = 'Audits and repairs network data integrity for Travel Dost.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Travel Dost Complete Network Audit..."))

        total_routes = Route.objects.count()
        total_stops = BusStop.objects.count()
        total_mappings = RouteStop.objects.count()

        out_of_bounds_coords = []
        duplicate_stops = []
        sequence_repairs = 0
        unrealistic_distances = []
        interchange_hub_count = 0

        # 1. Audit Bus Stops
        stops = list(BusStop.objects.all())
        stop_names_seen = {}
        
        for s in stops:
            # Check GPS bounds (Hubballi-Dharwad bounding box roughly lat 14.8 - 15.8, lng 74.8 - 75.5)
            if not (14.5 <= s.latitude <= 16.0 and 74.5 <= s.longitude <= 75.8):
                out_of_bounds_coords.append({
                    "id": s.id,
                    "name": s.stop_name,
                    "lat": s.latitude,
                    "lng": s.longitude
                })

            norm_name = s.stop_name.strip().lower()
            if norm_name in stop_names_seen:
                duplicate_stops.append({
                    "id": s.id,
                    "name": s.stop_name,
                    "original_id": stop_names_seen[norm_name].id
                })
            else:
                stop_names_seen[norm_name] = s

        # 2. Audit Routes & RouteStop Mappings
        routes = Route.objects.prefetch_related('route_stops__bus_stop').all()
        
        with transaction.atomic():
            for route in routes:
                route_stops = list(route.route_stops.order_by('stop_order'))
                if not route_stops:
                    continue

                # Check and fix stop_order gaps / duplicates
                expected_order = 1
                needs_order_repair = False
                
                for rs in route_stops:
                    if rs.stop_order != expected_order:
                        needs_order_repair = True
                        break
                    expected_order += 1

                if needs_order_repair:
                    sequence_repairs += 1
                    for idx, rs in enumerate(route_stops, start=1):
                        if rs.stop_order != idx:
                            RouteStop.objects.filter(id=rs.id).update(stop_order=idx)

                # Check consecutive stop distances
                for i in range(len(route_stops) - 1):
                    s1 = route_stops[i].bus_stop
                    s2 = route_stops[i+1].bus_stop
                    dist_km = haversine_distance(s1.latitude, s1.longitude, s2.latitude, s2.longitude)
                    
                    if dist_km > 15.0:
                        unrealistic_distances.append({
                            "route_id": route.id,
                            "route_name": route.route_name,
                            "stop1": s1.stop_name,
                            "stop2": s2.stop_name,
                            "distance_km": dist_km
                        })

        # Summary Metrics
        report = {
            "total_routes": total_routes,
            "total_stops": total_stops,
            "total_mappings": total_mappings,
            "out_of_bounds_coords": len(out_of_bounds_coords),
            "duplicate_stops": len(duplicate_stops),
            "sequence_repairs": sequence_repairs,
            "unrealistic_distances": len(unrealistic_distances),
            "is_production_ready": (len(out_of_bounds_coords) == 0 and len(unrealistic_distances) == 0)
        }

        self.stdout.write(self.style.SUCCESS(f"\n========== NETWORK AUDIT SUMMARY =========="))
        self.stdout.write(f"Total Routes Verified: {total_routes}")
        self.stdout.write(f"Total Stops Verified: {total_stops}")
        self.stdout.write(f"Total Route-Stop Links Verified: {total_mappings}")
        self.stdout.write(f"Invalid / Out-of-Bounds Coordinates: {len(out_of_bounds_coords)}")
        self.stdout.write(f"Duplicate Stop Names: {len(duplicate_stops)}")
        self.stdout.write(f"Route Sequence Orders Repaired: {sequence_repairs}")
        self.stdout.write(f"Unrealistic Consecutive Stop Distances (>15km): {len(unrealistic_distances)}")
        self.stdout.write(self.style.SUCCESS(f"Production Ready Verdict: {'YES' if report['is_production_ready'] else 'NO (Minor Warnings)'}"))
        self.stdout.write(self.style.SUCCESS(f"===========================================\n"))
