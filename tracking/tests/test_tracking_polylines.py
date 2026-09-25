from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from tracking.models import Bus, BusStop, Route, RouteStop, BusLocation


class TrackingPolylinesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create stops
        self.stop_a = BusStop.objects.create(
            stop_name="CBT Hubballi",
            latitude=15.3647,
            longitude=75.1240,
            area="Hubballi"
        )
        self.stop_b = BusStop.objects.create(
            stop_name="Unkal Lake",
            latitude=15.3780,
            longitude=75.1150,
            area="Hubballi"
        )
        self.stop_c = BusStop.objects.create(
            stop_name="Dharwad CBT",
            latitude=15.4580,
            longitude=75.0080,
            area="Dharwad"
        )

        # Create route
        self.route = Route.objects.create(
            route_name="Route 101: CBT Hubballi to Dharwad CBT",
            start_point=self.stop_a.stop_name,
            end_point=self.stop_c.stop_name
        )

        RouteStop.objects.create(route=self.route, bus_stop=self.stop_a, stop_order=1, distance_from_start_km=0.0)
        RouteStop.objects.create(route=self.route, bus_stop=self.stop_b, stop_order=2, distance_from_start_km=4.5)
        RouteStop.objects.create(route=self.route, bus_stop=self.stop_c, stop_order=3, distance_from_start_km=20.5)

        # Create offline bus with route assigned
        self.bus_offline = Bus.objects.create(
            bus_number="KA-25-F-1001",
            bus_name="Ordinary Express",
            bus_type="ORDINARY",
            tracking_status="OFFLINE",
            route=self.route
        )

        # Create live bus with ping
        self.bus_live = Bus.objects.create(
            bus_number="KA-25-F-1002",
            bus_name="Chigari BRTS",
            bus_type="BRTS",
            tracking_status="LIVE",
            trip_status="ACTIVE",
            route=self.route
        )
        BusLocation.objects.create(
            bus=self.bus_live,
            latitude=15.3700,
            longitude=75.1200,
            speed=32.0,
            heading=185.0
        )

    def test_offline_bus_tracking_status_returns_fallback_location_and_dual_polylines(self):
        url = reverse('api-bus-tracking-status', kwargs={'pk': self.bus_offline.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Coordinates must not be null
        self.assertIsNotNone(data.get('latest_location'))
        self.assertAlmostEqual(data['latest_location']['latitude'], 15.3647, places=3)
        self.assertAlmostEqual(data['latest_location']['longitude'], 75.1240, places=3)

        # Source and destination stops must be present
        self.assertIsNotNone(data.get('source_stop'))
        self.assertEqual(data['source_stop']['name'], "CBT Hubballi")
        self.assertIsNotNone(data.get('destination_stop'))
        self.assertEqual(data['destination_stop']['name'], "Dharwad CBT")

        # Source-to-destination points and bus-to-source points must be populated
        self.assertTrue(len(data.get('source_to_destination_points', [])) >= 2)
        self.assertTrue(len(data.get('bus_to_source_points', [])) >= 2)

    def test_live_bus_tracking_status_returns_live_location_and_bus_to_source_points(self):
        url = reverse('api-bus-tracking-status', kwargs={'pk': self.bus_live.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data.get('is_live'))
        self.assertAlmostEqual(data['latest_location']['latitude'], 15.3700, places=3)
        self.assertAlmostEqual(data['latest_location']['longitude'], 75.1200, places=3)

        # Bus to source points should start at live bus location and end at stop_a
        bus_to_source = data.get('bus_to_source_points', [])
        self.assertEqual(len(bus_to_source), 2)
        self.assertAlmostEqual(bus_to_source[0][0], 15.3700, places=3)
        self.assertAlmostEqual(bus_to_source[1][0], 15.3647, places=3)

    def test_passenger_live_status_api_returns_source_destination_and_non_null_coords(self):
        url = reverse('api-bus-live-status', kwargs={'bus_no': self.bus_offline.bus_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data.get('success'))
        self.assertIsNotNone(data.get('current_lat'))
        self.assertIsNotNone(data.get('current_lon'))
        self.assertAlmostEqual(data['current_lat'], 15.3647, places=3)
        self.assertAlmostEqual(data['current_lon'], 75.1240, places=3)
        self.assertIsNotNone(data.get('source_stop'))
        self.assertIsNotNone(data.get('destination_stop'))
