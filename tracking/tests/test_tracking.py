from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from tracking.models import User, BusStop, Route, RouteStop, Bus, Fare
from tracking.services.distance import haversine_distance
from tracking.services.route_finder import find_best_routes


class TravelDostTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test stops
        self.stop_kleit = BusStop.objects.create(
            stop_name="KLEIT", area="Vidya Nagar", latitude=15.3647, longitude=75.1240
        )
        self.stop_unkal = BusStop.objects.create(
            stop_name="Unkal Lake", area="Unkal", latitude=15.3780, longitude=75.1150
        )
        self.stop_dharwad = BusStop.objects.create(
            stop_name="Dharwad CBT", area="Dharwad", latitude=15.4580, longitude=75.0080
        )

        # Create test route
        self.route101 = Route.objects.create(
            route_name="Route 101 Test", start_point="KLEIT", end_point="Dharwad CBT"
        )
        RouteStop.objects.create(route=self.route101, bus_stop=self.stop_kleit, stop_order=1, distance_from_start_km=0.0)
        RouteStop.objects.create(route=self.route101, bus_stop=self.stop_unkal, stop_order=2, distance_from_start_km=3.0)
        RouteStop.objects.create(route=self.route101, bus_stop=self.stop_dharwad, stop_order=3, distance_from_start_km=18.0)

        # Create test bus
        self.bus101 = Bus.objects.create(
            bus_number="101-TEST", bus_name="NWKRTC Test Bus", route=self.route101, tracking_status="LIVE"
        )

        # Create test fare
        Fare.objects.create(
            route=self.route101, source_stop=self.stop_kleit, destination_stop=self.stop_dharwad, fare_amount=25.00
        )

    def test_haversine_distance(self):
        dist = haversine_distance(15.3647, 75.1240, 15.4580, 75.0080)
        self.assertTrue(10.0 < dist < 25.0)

    def test_direct_route_finding(self):
        res = find_best_routes(self.stop_kleit.id, self.stop_dharwad.id)
        self.assertEqual(res['total_routes_found'], 1)
        self.assertEqual(res['routes'][0]['transfers'], 0)
        self.assertEqual(res['routes'][0]['estimated_fare'], 25.00)

    def test_api_endpoints(self):
        # Test stops list API
        response = self.client.get('/api/stops/')
        self.assertEqual(response.status_code, 200)

        # Test stops autocomplete API
        response = self.client.get('/api/stops/autocomplete/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('stops', response.data)
        self.assertIn('KLEIT', response.data['stops'])

        # Test route search API
        response = self.client.get(f'/api/routes/search/?source={self.stop_kleit.id}&destination={self.stop_dharwad.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['total_options'], 1)
        self.assertEqual(len(response.data['top_routes']), 1)
        top_route = response.data['top_routes'][0]
        self.assertEqual(top_route['transfers'], 0)
        self.assertEqual(top_route['transfer_label'], 'Direct')
        self.assertTrue(len(top_route['legs']) > 0)
        leg = top_route['legs'][0]
        self.assertIn('bus_no', leg)
        self.assertIn('path_names', leg)
        self.assertIn('path_coords', leg)

        # Test nearby stops API
        response = self.client.get('/api/nearby-stops/?lat=15.3647&lng=75.1240')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data['nearby_stops']) > 0)
