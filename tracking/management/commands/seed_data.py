import csv
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
from tracking.models import User, BusStop, Route, RouteStop, Bus, GPSDevice, Fare, BusLocation


class Command(BaseCommand):
    help = 'Seeds database with realistic demo bus tracking data for Hubballi-Dharwad region (NWKRTC).'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Starting Travel Dost Seed Data Script ---'))

        # -------------------------------------------------------------
        # 1. CREATE USERS
        # -------------------------------------------------------------
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@traveldost.in',
                'first_name': 'System',
                'last_name': 'Administrator',
                'role': 'ADMIN',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created Superuser: admin / admin123'))

        driver_user, created = User.objects.get_or_create(
            username='driver1',
            defaults={
                'email': 'driver1@traveldost.in',
                'first_name': 'Ramesh',
                'last_name': 'Driver',
                'role': 'DRIVER',
            }
        )
        if created:
            driver_user.set_password('driver123')
            driver_user.save()
            self.stdout.write(self.style.SUCCESS('Created Driver User: driver1 / driver123'))

        passenger_user, created = User.objects.get_or_create(
            username='passenger1',
            defaults={
                'email': 'passenger@traveldost.in',
                'first_name': 'Anand',
                'last_name': 'Passenger',
                'role': 'PASSENGER',
            }
        )
        if created:
            passenger_user.set_password('passenger123')
            passenger_user.save()
            self.stdout.write(self.style.SUCCESS('Created Passenger User: passenger1 / passenger123'))

        # -------------------------------------------------------------
        # 2. CREATE BUS STOPS (Hubballi-Dharwad Landmarks)
        # -------------------------------------------------------------
        stops_data = [
            {"name": "CBT Hubballi", "area": "Hubballi City Center", "lat": 15.3480, "lng": 75.1400, "desc": "Central Bus Terminal Hubballi"},
            {"name": "Railway Station Hubballi", "area": "Station Road", "lat": 15.3430, "lng": 75.1480, "desc": "Hubballi Junction Railway Station"},
            {"name": "Hosur Bus Stop", "area": "Hosur Hubballi", "lat": 15.3500, "lng": 75.1350, "desc": "Hosur Circle Hubballi"},
            {"name": "Vidya Nagar Bus Stop", "area": "Vidya Nagar", "lat": 15.3590, "lng": 75.1280, "desc": "Vidya Nagar Hubballi"},
            {"name": "KLEIT Bus Stop", "area": "Vidya Nagar / Gokul Road", "lat": 15.3647, "lng": 75.1240, "desc": "KLE Technological Institute / KLE Society Campus"},
            {"name": "Unkal Lake Bus Stop", "area": "Unkal", "lat": 15.3780, "lng": 75.1150, "desc": "Unkal Lake Park Hubballi"},
            {"name": "Navanagar Bus Stop", "area": "Navanagar Highway", "lat": 15.4010, "lng": 75.0890, "desc": "Navanagar Hubballi-Dharwad Highway"},
            {"name": "Rayapur Bus Stop", "area": "Rayapur Industrial Area", "lat": 15.4120, "lng": 75.0750, "desc": "Rayapur Highway Circle"},
            {"name": "SDM Medical College Stop", "area": "Sattur Dharwad", "lat": 15.4250, "lng": 75.0450, "desc": "SDM Medical & Engineering Campus Sattur"},
            {"name": "Dharwad CBT", "area": "Dharwad Center", "lat": 15.4580, "lng": 75.0080, "desc": "Central Bus Terminal Dharwad"},
            {"name": "Raj Nagar Bus Stop", "area": "Raj Nagar Hubballi", "lat": 15.3680, "lng": 75.1520, "desc": "Raj Nagar Residential Area"},
            {"name": "Karnatak University Stop", "area": "KUD Campus Dharwad", "lat": 15.4420, "lng": 75.0020, "desc": "Karnatak University Dharwad Main Gate"},
        ]

        stops_dict = {}
        for s in stops_data:
            stop_obj, _ = BusStop.objects.get_or_create(
                stop_name=s["name"],
                defaults={
                    "area": s["area"],
                    "latitude": s["lat"],
                    "longitude": s["lng"],
                    "description": s["desc"]
                }
            )
            stops_dict[s["name"]] = stop_obj

        self.stdout.write(self.style.SUCCESS(f'Populated {len(stops_dict)} Bus Stops.'))

        # -------------------------------------------------------------
        # 3. CREATE ROUTES
        # -------------------------------------------------------------
        r1, _ = Route.objects.get_or_create(
            route_name="Route 101: Hubballi CBT ➔ Dharwad CBT",
            defaults={
                "start_point": "CBT Hubballi",
                "end_point": "Dharwad CBT",
                "description": "DEMO DATA — Primary Hubballi to Dharwad Corridor via KLEIT and Unkal"
            }
        )

        r2, _ = Route.objects.get_or_create(
            route_name="Route 202: KLEIT ➔ Raj Nagar",
            defaults={
                "start_point": "KLEIT Bus Stop",
                "end_point": "Raj Nagar Bus Stop",
                "description": "DEMO DATA — Educational Hub to Raj Nagar via CBT Hubballi"
            }
        )

        r3, _ = Route.objects.get_or_create(
            route_name="Route 303: Chigari BRTS Express",
            defaults={
                "start_point": "CBT Hubballi",
                "end_point": "Dharwad CBT",
                "description": "DEMO DATA — High Speed Bus Rapid Transit Corridor"
            }
        )

        # -------------------------------------------------------------
        # 4. CREATE ROUTE STOPS ORDERING
        # -------------------------------------------------------------
        # Route 101 Stops Sequence
        r1_stops = [
            ("CBT Hubballi", 0.0),
            ("Hosur Bus Stop", 1.8),
            ("Vidya Nagar Bus Stop", 3.2),
            ("KLEIT Bus Stop", 4.5),
            ("Unkal Lake Bus Stop", 6.1),
            ("Navanagar Bus Stop", 9.8),
            ("Rayapur Bus Stop", 12.4),
            ("SDM Medical College Stop", 15.6),
            ("Dharwad CBT", 20.2)
        ]
        RouteStop.objects.filter(route=r1).delete()
        for idx, (stop_name, dist) in enumerate(r1_stops, 1):
            RouteStop.objects.create(
                route=r1,
                bus_stop=stops_dict[stop_name],
                stop_order=idx,
                distance_from_start_km=dist
            )

        # Route 202 Stops Sequence
        r2_stops = [
            ("KLEIT Bus Stop", 0.0),
            ("Vidya Nagar Bus Stop", 1.2),
            ("Hosur Bus Stop", 2.5),
            ("CBT Hubballi", 4.1),
            ("Railway Station Hubballi", 5.2),
            ("Raj Nagar Bus Stop", 7.5)
        ]
        RouteStop.objects.filter(route=r2).delete()
        for idx, (stop_name, dist) in enumerate(r2_stops, 1):
            RouteStop.objects.create(
                route=r2,
                bus_stop=stops_dict[stop_name],
                stop_order=idx,
                distance_from_start_km=dist
            )

        # Route 303 BRTS Stops Sequence
        r3_stops = [
            ("CBT Hubballi", 0.0),
            ("Unkal Lake Bus Stop", 5.5),
            ("Navanagar Bus Stop", 9.2),
            ("Rayapur Bus Stop", 12.0),
            ("SDM Medical College Stop", 15.0),
            ("Dharwad CBT", 19.8)
        ]
        RouteStop.objects.filter(route=r3).delete()
        for idx, (stop_name, dist) in enumerate(r3_stops, 1):
            RouteStop.objects.create(
                route=r3,
                bus_stop=stops_dict[stop_name],
                stop_order=idx,
                distance_from_start_km=dist
            )

        self.stdout.write(self.style.SUCCESS('Configured RouteStops for Routes 101, 202, 303.'))

        # -------------------------------------------------------------
        # 5. CREATE BUSES & GPS DEVICES
        # -------------------------------------------------------------
        bus101, _ = Bus.objects.get_or_create(
            bus_number="101",
            defaults={
                "bus_name": "NWKRTC City Bus 101 (KA-25-F-101)",
                "bus_type": "ORDINARY",
                "route": r1,
                "tracking_status": "LIVE"
            }
        )
        bus101.route = r1
        bus101.tracking_status = "LIVE"
        bus101.save()

        bus202, _ = Bus.objects.get_or_create(
            bus_number="202",
            defaults={
                "bus_name": "NWKRTC Express Bus 202 (KA-25-F-202)",
                "bus_type": "EXPRESS",
                "route": r2,
                "tracking_status": "LAST_SEEN"
            }
        )
        bus202.route = r2
        bus202.save()

        bus303, _ = Bus.objects.get_or_create(
            bus_number="303",
            defaults={
                "bus_name": "Chigari BRTS Bus 303 (KA-25-F-303)",
                "bus_type": "BRTS",
                "route": r3,
                "tracking_status": "OFFLINE"
            }
        )
        bus303.route = r3
        bus303.save()

        # GPS Device assignment (Mobile phone prototype)
        device, _ = GPSDevice.objects.get_or_create(
            device_id="DEV-MOBILE-01",
            defaults={
                "device_name": "Naveet Mobile Device (Android/iOS)",
                "assigned_bus": bus101,
                "user": driver_user,
                "is_active": True,
                "last_seen": timezone.now()
            }
        )
        device.assigned_bus = bus101
        device.save()

        # Seed initial location for Bus 101 near KLEIT
        BusLocation.objects.create(
            bus=bus101,
            latitude=15.3647,
            longitude=75.1240,
            speed=32.0,
            heading=180.0,
            timestamp=timezone.now()
        )

        # -------------------------------------------------------------
        # 6. FARE MATRIX
        # -------------------------------------------------------------
        Fare.objects.all().delete()

        # Fares for Route 101
        Fare.objects.create(route=r1, source_stop=stops_dict["CBT Hubballi"], destination_stop=stops_dict["Dharwad CBT"], fare_amount=35.00, fare_type="Standard Ordinary")
        Fare.objects.create(route=r1, source_stop=stops_dict["KLEIT Bus Stop"], destination_stop=stops_dict["Dharwad CBT"], fare_amount=25.00, fare_type="Standard Ordinary")
        Fare.objects.create(route=r1, source_stop=stops_dict["KLEIT Bus Stop"], destination_stop=stops_dict["Raj Nagar Bus Stop"], fare_amount=18.00, fare_type="Standard Ordinary")

        # Fares for Route 202
        Fare.objects.create(route=r2, source_stop=stops_dict["KLEIT Bus Stop"], destination_stop=stops_dict["Raj Nagar Bus Stop"], fare_amount=15.00, fare_type="Standard Ordinary")
        Fare.objects.create(route=r2, source_stop=stops_dict["KLEIT Bus Stop"], destination_stop=stops_dict["CBT Hubballi"], fare_amount=10.00, fare_type="Standard Ordinary")

        self.stdout.write(self.style.SUCCESS('Created Fares matrix.'))
        self.stdout.write(self.style.SUCCESS('Successfully completed Travel Dost demo data seeding!'))
