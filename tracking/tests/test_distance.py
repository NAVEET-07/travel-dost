import math
from django.test import TestCase
from tracking.services.distance import (
    haversine_distance,
    validate_coordinates,
    calculate_consecutive_stops_distance,
    calculate_walk_distance,
    format_distance,
    audit_stop_coordinates_data
)


class DistanceServiceTestCase(TestCase):

    def test_validate_coordinates_valid(self):
        is_valid, err = validate_coordinates(15.3647, 75.1240)
        self.assertTrue(is_valid)
        self.assertIsNone(err)

    def test_validate_coordinates_missing_lat(self):
        is_valid, err = validate_coordinates(None, 75.1240)
        self.assertFalse(is_valid)
        self.assertIn("Missing", err)

    def test_validate_coordinates_missing_lon(self):
        is_valid, err = validate_coordinates(15.3647, None)
        self.assertFalse(is_valid)
        self.assertIn("Missing", err)

    def test_validate_coordinates_lat_above_90(self):
        is_valid, err = validate_coordinates(91.0, 75.1240)
        self.assertFalse(is_valid)
        self.assertIn("range", err)

    def test_validate_coordinates_lat_below_minus_90(self):
        is_valid, err = validate_coordinates(-91.0, 75.1240)
        self.assertFalse(is_valid)
        self.assertIn("range", err)

    def test_validate_coordinates_lon_above_180(self):
        is_valid, err = validate_coordinates(15.3647, 181.0)
        self.assertFalse(is_valid)
        self.assertIn("range", err)

    def test_validate_coordinates_lon_below_minus_180(self):
        is_valid, err = validate_coordinates(15.3647, -181.0)
        self.assertFalse(is_valid)
        self.assertIn("range", err)

    def test_haversine_known_points(self):
        # Known coordinates: Hubballi CBT (15.3647, 75.1240) to Dharwad CBT (15.4589, 75.0078)
        # Expected great-circle distance is approx 16.3 km
        dist = haversine_distance(15.3647, 75.1240, 15.4589, 75.0078)
        self.assertAlmostEqual(dist, 16.32, delta=0.5)

    def test_haversine_symmetry(self):
        dist_a_b = haversine_distance(15.3647, 75.1240, 15.4589, 75.0078)
        dist_b_a = haversine_distance(15.4589, 75.0078, 15.3647, 75.1240)
        self.assertAlmostEqual(dist_a_b, dist_b_a, places=6)

    def test_haversine_zero_distance(self):
        dist = haversine_distance(15.3647, 75.1240, 15.3647, 75.1240)
        self.assertEqual(dist, 0.0)

    def test_consecutive_stops_distance(self):
        stop_a = {"lat": 15.3647, "lng": 75.1240}
        stop_b = {"lat": 15.3800, "lng": 75.1100}
        stop_c = {"lat": 15.4000, "lng": 75.0900}

        d_ab = haversine_distance(15.3647, 75.1240, 15.3800, 75.1100)
        d_bc = haversine_distance(15.3800, 75.1100, 15.4000, 75.0900)

        stops = [stop_a, stop_b, stop_c]
        total_calculated = calculate_consecutive_stops_distance(stops)
        expected_total = round(d_ab + d_bc, 2)

        self.assertEqual(total_calculated, expected_total)

    def test_format_distance(self):
        self.assertEqual(format_distance(0.35), "350 m")
        self.assertEqual(format_distance(0.85), "850 m")
        self.assertEqual(format_distance(1.20), "1.20 km")
        self.assertEqual(format_distance(2.47), "2.47 km")

    def test_calculate_walk_distance(self):
        p1 = {"lat": 15.3647, "lng": 75.1240}
        p2 = {"lat": 15.3660, "lng": 75.1250}

        dist_km, dist_str = calculate_walk_distance(p1, p2)
        self.assertGreater(dist_km, 0.0)
        self.assertTrue(dist_str.endswith("m") or dist_str.endswith("km"))

    def test_audit_stop_coordinates_data(self):
        results = audit_stop_coordinates_data()
        self.assertIn("summary", results)
        self.assertIn("total_stops", results["summary"])
        self.assertIn("valid_stops_count", results["summary"])
        self.assertIn("suspicious_distances_count", results["summary"])
