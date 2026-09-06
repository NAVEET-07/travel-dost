import json
from django.test import TestCase
from django.contrib.auth import authenticate
from rest_framework.test import APIClient
from tracking.models import User, BusStop, Route, RouteStop, Bus, BusLocation, BusTrackingSession


class LiveTrackingSystemTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create driver user
        self.driver_user = User.objects.create_user(
            username="driver_test",
            password="driver_password123",
            role="DRIVER",
            email="driver@test.com",
            phone_number="9876543210"
        )

        # Create passenger user
        self.passenger_user = User.objects.create_user(
            username="passenger_test",
            password="passenger_password123",
            role="USER",
            email="passenger@test.com"
        )

        # Create route and stops
        self.stop_a = BusStop.objects.create(
            stop_name="Hubballi CBT", area="CBT", latitude=15.3530, longitude=75.1410
        )
        self.stop_b = BusStop.objects.create(
            stop_name="Navanagar", area="Navanagar", latitude=15.3920, longitude=75.1050
        )
        self.stop_c = BusStop.objects.create(
            stop_name="Dharwad CBT", area="Dharwad", latitude=15.4580, longitude=75.0080
        )

        self.route = Route.objects.create(
            route_name="Corridor 100", start_point="Hubballi CBT", end_point="Dharwad CBT"
        )
        RouteStop.objects.create(route=self.route, bus_stop=self.stop_a, stop_order=1, distance_from_start_km=0.0)
        RouteStop.objects.create(route=self.route, bus_stop=self.stop_b, stop_order=2, distance_from_start_km=8.0)
        RouteStop.objects.create(route=self.route, bus_stop=self.stop_c, stop_order=3, distance_from_start_km=20.0)

        # Create bus assigned to driver, initially SCHEDULED (not active trip)
        self.bus = Bus.objects.create(
            bus_number="KA-25-F-9999",
            bus_name="Chigari Express",
            route=self.route,
            driver=self.driver_user,
            tracking_status="OFFLINE",
            trip_status="SCHEDULED"
        )

    def test_user_registration_direct_persistence(self):
        """Test zero-mock registration with verified direct DB persistence."""
        reg_payload = {
            "username": "new_commuter_77",
            "password": "SecurePassword456!",
            "role": "USER",
            "first_name": "Ravi",
            "last_name": "Kumar",
            "phone_number": "9123456780"
        }
        response = self.client.post('/api/auth/register/', reg_payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data.get('status'), 'success')

        # Directly verify user exists in DB
        user_in_db = User.objects.filter(username="new_commuter_77").first()
        self.assertIsNotNone(user_in_db)
        self.assertEqual(user_in_db.first_name, "Ravi")
        self.assertEqual(user_in_db.role, "USER")

        # Verify password correctly hashed and authenticatable
        authenticated = authenticate(username="new_commuter_77", password="SecurePassword456!")
        self.assertIsNotNone(authenticated)

    def test_ghost_bus_elimination_and_trip_lifecycle(self):
        """
        Verify ghost buses are never rendered:
        Only buses on active trips (ACTIVE, IN_PROGRESS, IN_TRANSIT) with status LIVE appear.
        """
        # 1. Bus is SCHEDULED & OFFLINE -> Must NOT appear in live buses
        live_resp = self.client.get('/api/buses/?status=LIVE')
        self.assertEqual(live_resp.status_code, 200)
        bus_ids = [b['id'] for b in live_resp.data]
        self.assertNotIn(self.bus.id, bus_ids)

        # Tracking status API must report is_live = False
        status_resp = self.client.get(f'/api/buses/{self.bus.id}/tracking-status/')
        self.assertEqual(status_resp.status_code, 200)
        self.assertFalse(status_resp.data['is_live'])

        # 2. Driver logs in and clicks 'Start Trip'
        self.client.force_authenticate(user=self.driver_user)
        start_resp = self.client.post('/api/driver/trip/start/', {'bus_id': self.bus.id}, format='json')
        self.assertEqual(start_resp.status_code, 200)
        self.assertEqual(start_resp.data.get('trip_status'), 'ACTIVE')

        # Refresh bus state from DB
        self.bus.refresh_from_db()
        self.assertEqual(self.bus.trip_status, 'ACTIVE')
        self.assertEqual(self.bus.tracking_status, 'LIVE')

        # Verify active BusTrackingSession created
        session = BusTrackingSession.objects.filter(bus=self.bus, status='ACTIVE').first()
        self.assertIsNotNone(session)

        # 3. Now the bus IS LIVE and MUST appear in active live bus listings
        self.client.force_authenticate(user=None)
        live_resp = self.client.get('/api/buses/?status=LIVE')
        self.assertEqual(live_resp.status_code, 200)
        bus_ids = [b['id'] for b in live_resp.data]
        self.assertIn(self.bus.id, bus_ids)

        status_resp = self.client.get(f'/api/buses/{self.bus.id}/tracking-status/')
        self.assertEqual(status_resp.status_code, 200)
        self.assertTrue(status_resp.data['is_live'])
        self.assertEqual(status_resp.data['trip_status'], 'ACTIVE')

        # 4. Driver clicks 'End Trip'
        self.client.force_authenticate(user=self.driver_user)
        end_resp = self.client.post('/api/driver/trip/end/', {'bus_id': self.bus.id}, format='json')
        self.assertEqual(end_resp.status_code, 200)

        self.bus.refresh_from_db()
        self.assertEqual(self.bus.trip_status, 'COMPLETED')
        self.assertEqual(self.bus.tracking_status, 'OFFLINE')

        # Bus must be immediately removed from live buses (no ghost bus)
        self.client.force_authenticate(user=None)
        live_resp = self.client.get('/api/buses/?status=LIVE')
        bus_ids = [b['id'] for b in live_resp.data]
        self.assertNotIn(self.bus.id, bus_ids)

        status_resp = self.client.get(f'/api/buses/{self.bus.id}/tracking-status/')
        self.assertFalse(status_resp.data['is_live'])

    def test_three_second_gps_breadcrumbs_streaming(self):
        """
        Verify driver 3-second GPS updates persist high-accuracy telemetry,
        update bus location, and maintain real-time breadcrumbs.
        """
        # Start trip
        self.client.force_authenticate(user=self.driver_user)
        self.client.post('/api/driver/trip/start/', {'bus_id': self.bus.id}, format='json')

        # Simulate 3 consecutive 3-second GPS telemetry frames
        coords = [
            {"latitude": 15.3530, "longitude": 75.1410, "speed": 28.5, "heading": 45.0, "timestamp": "2026-09-06T12:00:00Z"},
            {"latitude": 15.3550, "longitude": 75.1390, "speed": 34.0, "heading": 48.0, "timestamp": "2026-09-06T12:00:03Z"},
            {"latitude": 15.3575, "longitude": 75.1370, "speed": 36.2, "heading": 50.0, "timestamp": "2026-09-06T12:00:06Z"},
        ]

        for pt in coords:
            resp = self.client.post(
                '/api/driver/trip/update-location/',
                {
                    "bus_id": self.bus.id,
                    "latitude": pt["latitude"],
                    "longitude": pt["longitude"],
                    "speed": pt["speed"],
                    "heading": pt["heading"],
                    "timestamp": pt["timestamp"]
                },
                format='json'
            )
            self.assertEqual(resp.status_code, 200)

        # Verify DB persisted all 3 location records
        locations = BusLocation.objects.filter(bus=self.bus).order_by('timestamp')
        self.assertEqual(locations.count(), 3)
        latest_loc = locations.last()
        self.assertAlmostEqual(float(latest_loc.latitude), 15.3575, places=4)
        self.assertAlmostEqual(float(latest_loc.speed), 36.2, places=1)

        # Verify tracking status API returns chronological breadcrumbs
        self.client.force_authenticate(user=None)
        status_resp = self.client.get(f'/api/buses/{self.bus.id}/tracking-status/')
        self.assertEqual(status_resp.status_code, 200)
        breadcrumbs = status_resp.data.get('traveled_breadcrumbs', [])
        self.assertTrue(len(breadcrumbs) >= 3)
        self.assertAlmostEqual(breadcrumbs[0][0], 15.3530, places=3)
        self.assertAlmostEqual(breadcrumbs[-1][0], 15.3575, places=3)

    def test_route_finder_road_geometry_primary_polyline(self):
        """
        Verify route search returns unified road-snapped geometry
        without zig-zag loops between source and destination.
        """
        resp = self.client.get(f'/api/routes/search/?source={self.stop_a.id}&destination={self.stop_c.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertTrue(len(resp.data['top_routes']) >= 1)

        primary_route = resp.data['top_routes'][0]
        self.assertEqual(primary_route['transfers'], 0)
        self.assertIn('road_geometry', primary_route)
        self.assertTrue(isinstance(primary_route['road_geometry'], list))
        self.assertTrue(len(primary_route['road_geometry']) >= 2)
