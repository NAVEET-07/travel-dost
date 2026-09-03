import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from tracking.services.distance import audit_stop_coordinates_data


class Command(BaseCommand):
    help = "Audits all BusStop coordinates and RouteStop consecutive distances in Travel Dost database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Display full line-by-line diagnostic details for every duplicate group and suspicious segment.'
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        self.stdout.write(self.style.MIGRATE_HEADING("=== TRAVEL DOST BUS STOP COORDINATE & DISTANCE AUDIT ==="))

        results = audit_stop_coordinates_data()
        summary = results["summary"]

        self.stdout.write(f"Total stops: {summary['total_stops']}")
        self.stdout.write(f"Valid coordinates: {summary['valid_stops_count']}")
        self.stdout.write(f"Missing coordinates: {summary['missing_coords_count']}")
        self.stdout.write(f"Invalid coordinates: {summary['invalid_coords_count']}")
        self.stdout.write(f"Duplicate-coordinate groups: {summary['duplicate_coords_groups_count']}")
        self.stdout.write(f"Suspicious segments: {summary['suspicious_distances_count']}")
        self.stdout.write(f"Routes audited: {summary['total_routes_audited']}")
        self.stdout.write(f"Route-stop segments: {summary['total_route_segments']}")

        self.stdout.write(self.style.MIGRATE_LABEL("\nDuplicate Classification Breakdown:"))
        for cat, cnt in summary["duplicate_classification_breakdown"].items():
            self.stdout.write(f"  {cat}: {cnt}")

        self.stdout.write(self.style.MIGRATE_LABEL("\nSuspicious Segment Classification Breakdown:"))
        for cat, cnt in summary["suspicious_classification_breakdown"].items():
            self.stdout.write(f"  {cat}: {cnt}")

        # Export machine-readable JSON report coordinate_audit_report.json
        report_path = os.path.join(settings.BASE_DIR, "coordinate_audit_report.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f"\n[Export] Machine-readable report saved to: {report_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n[Export Error] Could not write report JSON: {e}"))

        if verbose:
            if results["duplicate_coordinates"]:
                self.stdout.write(self.style.WARNING("\n=== VERBOSE: DUPLICATE COORDINATE GROUPS ==="))
                for idx, dup in enumerate(results["duplicate_coordinates"], 1):
                    self.stdout.write(
                        f"\n[{idx}] Coords: ({dup['latitude']}, {dup['longitude']}) - Class: {dup['classification']}\n"
                        f"    Reason: {dup['classification_reason']}\n"
                        f"    Stops in group ({dup['stops_count']}):"
                    )
                    for st in dup["stops"]:
                        s_name = str(st['name']).encode('ascii', errors='replace').decode('ascii')
                        s_area = str(st['area']).encode('ascii', errors='replace').decode('ascii')
                        self.stdout.write(f"      - ID {st['id']}: {s_name} ({s_area}) [Route Usages: {st['route_usage_count']}]")

            if results["suspicious_segments"]:
                self.stdout.write(self.style.WARNING("\n=== VERBOSE: SUSPICIOUS CONSECUTIVE-STOP SEGMENTS ==="))
                for idx, seg in enumerate(results["suspicious_segments"], 1):
                    r_name = str(seg['route_name']).encode('ascii', errors='replace').decode('ascii')
                    sa_name = str(seg['stop_a']['name']).encode('ascii', errors='replace').decode('ascii')
                    sb_name = str(seg['stop_b']['name']).encode('ascii', errors='replace').decode('ascii')
                    self.stdout.write(
                        f"\n[{idx}] Route: {r_name} (ID: {seg['route_id']})\n"
                        f"    Warning Type: {seg['warning_type']}\n"
                        f"    Class: {seg['classification']}\n"
                        f"    Reason: {seg['classification_reason']}\n"
                        f"    Stop A: {sa_name} (ID: {seg['stop_a']['id']}) @ ({seg['stop_a']['latitude']}, {seg['stop_a']['longitude']}) [Route Usages: {seg['stop_a']['route_usage_count']}]\n"
                        f"    Stop B: {sb_name} (ID: {seg['stop_b']['id']}) @ ({seg['stop_b']['latitude']}, {seg['stop_b']['longitude']}) [Route Usages: {seg['stop_b']['route_usage_count']}]\n"
                        f"    Calculated Haversine Distance: {seg['haversine_distance_km']} km"
                    )

        self.stdout.write(self.style.SUCCESS("\n=== AUDIT COMPLETED SUCCESSFULLY ==="))
