from django.test import TestCase
from tracking.services.trip_lifecycle import TripLifecycleEngine, TripState, haversine_distance_meters


class TripLifecycleAnnouncerTests(TestCase):
    def setUp(self):
        # Create ordered 6-stop test route
        # Stop 0 (Pickup): CBT (15.3444, 75.1452)
        # Stop 1: Corporation (15.3514, 75.1418)
        # Stop 2: Court (15.3524, 75.1391)
        # Stop 3: Deshpande Nagar (15.3560, 75.1385)
        # Stop 4: Ganesh Temple (15.3620, 75.1370)
        # Stop 5 (Destination): Raj Nagar (15.3714, 75.1281)
        self.route_stops = [
            {'id': 1, 'name': 'CBT Terminal', 'lat': 15.344400, 'lng': 75.145200},
            {'id': 2, 'name': 'Corporation Circle', 'lat': 15.351400, 'lng': 75.141800},
            {'id': 3, 'name': 'Court Circle', 'lat': 15.352400, 'lng': 75.139100},
            {'id': 4, 'name': 'Deshpande Nagar', 'lat': 15.356000, 'lng': 75.138500},
            {'id': 5, 'name': 'Ganesh Temple', 'lat': 15.362000, 'lng': 75.137000},
            {'id': 6, 'name': 'Raj Nagar', 'lat': 15.371400, 'lng': 75.128100}
        ]

        self.announcements = []
        self.state_changes = []

        def record_announcement(msg, atype, meta):
            self.announcements.append({'message': msg, 'type': atype, 'meta': meta})

        def record_state_change(old_s, new_s, meta):
            self.state_changes.append({'old': old_s, 'new': new_s, 'meta': meta})

        self.engine = TripLifecycleEngine(
            route_stops=self.route_stops,
            pickup_stop_id=1,        # CBT Terminal
            destination_stop_id=6,   # Raj Nagar (5 stops away)
            initial_passenger_gps={'latitude': 15.344400, 'longitude': 75.145200, 'speed': 0.0},
            on_announcement=record_announcement,
            on_state_change=record_state_change
        )

    def test_haversine_distance_meters_accuracy(self):
        """Verify high-accuracy meter distance calculation."""
        p1 = (15.344400, 75.145200)
        p2 = (15.344400, 75.146200) # ~107 meters east
        dist = haversine_distance_meters(p1[0], p1[1], p2[0], p2[1])
        self.assertTrue(100.0 <= dist <= 115.0)

    def test_preboarding_proximity_announcements(self):
        """
        1. Pre-boarding proximity:
        - 100-150m: Approaching alert
        - 30-50m: Imminent alert
        - <20m near zero speed: Arrived / Boarding alert
        """
        self.assertEqual(self.engine.state, TripState.WAITING_FOR_BUS)

        # 1. Bus at ~130 meters away from pickup stop (15.3444, 75.1452)
        # Lat offset ~0.0011 deg ~ 122 meters
        self.engine.update_driver_gps(15.345500, 75.145200, speed=25.0)
        self.assertEqual(self.engine.state, TripState.BUS_ARRIVING)
        self.assertTrue(any(a['type'] == 'PRE_BOARDING_APPROACHING' for a in self.announcements))
        self.assertIn("arriving at your stop shortly", self.announcements[0]['message'])

        # 2. Bus at ~40 meters away (30m - 50m)
        # Lat offset 0.00035 deg ~ 38 meters
        self.engine.update_driver_gps(15.344750, 75.145200, speed=15.0)
        self.assertTrue(any(a['type'] == 'PRE_BOARDING_IMMINENT' for a in self.announcements))
        self.assertIn("within 50 meters", [a['message'] for a in self.announcements if a['type'] == 'PRE_BOARDING_IMMINENT'][0])

        # 3. Bus arrives at stop (< 20m) with near zero speed (< 6 km/h)
        self.engine.update_driver_gps(15.344450, 75.145200, speed=2.0)
        self.assertTrue(any(a['type'] == 'PRE_BOARDING_ARRIVED' for a in self.announcements))
        self.assertIn("has arrived at your stop. Please board", [a['message'] for a in self.announcements if a['type'] == 'PRE_BOARDING_ARRIVED'][0])

    def test_hysteresis_anti_spam_buffer(self):
        """
        Verify that jitter fluctuations around 40-50m do not duplicate announcements.
        """
        # First trigger at 42m
        self.engine.update_driver_gps(15.344780, 75.145200, speed=15.0)
        initial_count = len(self.announcements)

        # Fluctuations within range
        self.engine.update_driver_gps(15.344800, 75.145200, speed=14.0)
        self.engine.update_driver_gps(15.344760, 75.145200, speed=13.0)
        self.engine.update_driver_gps(15.344790, 75.145200, speed=12.0)

        # Count of imminent announcements must remain strictly 1
        imminent_announcements = [a for a in self.announcements if a['type'] == 'PRE_BOARDING_IMMINENT']
        self.assertEqual(len(imminent_announcements), 1)

    def test_automatic_trip_start_sync(self):
        """
        2. Automatic Trip Start:
        Driver and passenger within 30m AND speed > 10 km/h away from pickup point.
        """
        # Bus arrived at pickup point
        self.engine.update_driver_gps(15.344410, 75.145200, speed=1.0)
        # Passenger is boarding (GPS matching bus location)
        self.engine.update_passenger_gps(15.344415, 75.145200, speed=1.0)

        # Bus starts moving away (> 10 km/h, distance > 20m from stop)
        self.engine.update_driver_gps(15.344800, 75.145200, speed=24.0)
        # Passenger GPS moves with bus
        self.engine.update_passenger_gps(15.344800, 75.145200, speed=24.0)
        # Trigger again to process sync
        self.engine.update_driver_gps(15.344850, 75.145200, speed=26.0)

        self.assertEqual(self.engine.state, TripState.BOARDED_TRIP_ACTIVE)
        trip_started = [a for a in self.announcements if a['type'] == 'TRIP_STARTED']
        self.assertEqual(len(trip_started), 1)
        self.assertIn("Trip started. Welcome aboard!", trip_started[0]['message'])
        self.assertIn("Raj Nagar", trip_started[0]['message'])

        # Next stop departure announcement
        next_stop_announcements = [a for a in self.announcements if a['type'] == 'NEXT_STOP_ANNOUNCEMENT']
        self.assertTrue(len(next_stop_announcements) >= 1)
        self.assertIn("Corporation Circle", next_stop_announcements[0]['message'])

    def test_en_route_stop_progression_and_destination_countdown(self):
        """
        3 & 4. En-Route Dynamic Stop Progression & Relative Destination Countdown:
        - Approaching intermediate stops (within 100m)
        - Departing stop: 'Next stop is: [Next Stop Name]'
        - Countdown 3 stops away: 'Notice: Your destination [Name] is approaching in 3 stops.'
        - Countdown 2 stops away: 'Your destination is approaching after the next stop (2 stops away).'
        - Countdown 1 stop away: 'Next stop is your destination: [Name]. Please prepare your belongings.'
        - Destination Arrival (< 20m): 'You have arrived at your destination: [Name]. Please safely exit the bus.'
        """
        # Start the trip
        self.engine.update_driver_gps(15.344400, 75.145200, speed=1.0)
        self.engine.update_passenger_gps(15.344400, 75.145200, speed=1.0)
        self.engine.update_passenger_gps(15.344630, 75.145200, speed=22.0)
        self.engine.update_driver_gps(15.344635, 75.145200, speed=22.0) # Trip starts
        self.assertEqual(self.engine.state, TripState.BOARDED_TRIP_ACTIVE)

        # -----------------------------------------------------------------
        # Stop 1 (Corporation Circle: 15.351400, 75.141800)
        # -----------------------------------------------------------------
        # Bus approaches Stop 1 within 100m (lat ~15.350800, dist ~70m)
        self.engine.update_driver_gps(15.350800, 75.141800, speed=20.0)
        self.assertTrue(any(a['type'] == 'STOP_APPROACHING' and 'Corporation Circle' in a['message'] for a in self.announcements))

        # Bus halts and departs Stop 1 (dist <= 25m)
        self.engine.update_driver_gps(15.351400, 75.141800, speed=5.0)

        # Departed Stop 1 -> Current is now Stop 1, Next is Stop 2 (Court Circle)
        # Destination is Stop 5 (Raj Nagar).
        # Stops remaining: 5 - 1 = 4 stops away.
        self.assertEqual(self.engine.current_stop_index, 1)
        self.assertEqual(self.engine.next_stop_index, 2)

        # -----------------------------------------------------------------
        # Stop 2 (Court Circle: 15.352400, 75.139100)
        # -----------------------------------------------------------------
        # Bus reaches and departs Stop 2
        self.engine.update_driver_gps(15.352400, 75.139100, speed=4.0)

        # Current stop is now Stop 2. Next is Stop 3 (Deshpande Nagar).
        # Stops remaining: 5 - 2 = 3 stops away!
        # COUNTDOWN 3 STOPS MUST TRIGGER!
        countdown_3 = [a for a in self.announcements if a['type'] == 'COUNTDOWN_3_STOPS']
        self.assertEqual(len(countdown_3), 1)
        self.assertIn("approaching in 3 stops", countdown_3[0]['message'])
        self.assertIn("Raj Nagar", countdown_3[0]['message'])
        self.assertEqual(self.engine.state, TripState.APPROACHING_DESTINATION)

        # -----------------------------------------------------------------
        # Stop 3 (Deshpande Nagar: 15.356000, 75.138500)
        # -----------------------------------------------------------------
        # Bus reaches and departs Stop 3
        self.engine.update_driver_gps(15.356000, 75.138500, speed=5.0)

        # Current stop is now Stop 3. Next is Stop 4 (Ganesh Temple).
        # Stops remaining: 5 - 3 = 2 stops away!
        # COUNTDOWN 2 STOPS MUST TRIGGER!
        countdown_2 = [a for a in self.announcements if a['type'] == 'COUNTDOWN_2_STOPS']
        self.assertEqual(len(countdown_2), 1)
        self.assertIn("after the next stop (2 stops away)", countdown_2[0]['message'])

        # -----------------------------------------------------------------
        # Stop 4 (Ganesh Temple: 15.362000, 75.137000) - Penultimate Stop
        # -----------------------------------------------------------------
        # Bus reaches and departs Stop 4
        self.engine.update_driver_gps(15.362000, 75.137000, speed=5.0)

        # Current stop is now Stop 4. Next is Stop 5 (Raj Nagar - Destination).
        # Stops remaining: 5 - 4 = 1 stop away!
        # COUNTDOWN 1 STOP MUST TRIGGER!
        countdown_1 = [a for a in self.announcements if a['type'] == 'COUNTDOWN_1_STOP']
        self.assertEqual(len(countdown_1), 1)
        self.assertIn("Next stop is your destination: Raj Nagar. Please prepare your belongings.", countdown_1[0]['message'])

        # -----------------------------------------------------------------
        # Stop 5 (Destination: Raj Nagar: 15.371400, 75.128100)
        # -----------------------------------------------------------------
        # Bus enters final destination geofence (< 20m)
        self.engine.update_driver_gps(15.371405, 75.128105, speed=8.0)

        # Must trigger final arrival announcement and complete trip
        arrival_announcements = [a for a in self.announcements if a['type'] == 'DESTINATION_ARRIVED']
        self.assertEqual(len(arrival_announcements), 1)
        self.assertIn("You have arrived at your destination: Raj Nagar. Please safely exit the bus.", arrival_announcements[0]['message'])
        self.assertEqual(self.engine.state, TripState.COMPLETED)
        self.assertTrue(self.engine.get_status_snapshot()['is_completed'])

    def test_short_trip_two_stops(self):
        """Verify countdown and stop progression on short 2-stop trips."""
        short_engine = TripLifecycleEngine(
            route_stops=self.route_stops,
            pickup_stop_id=1,        # CBT (Index 0)
            destination_stop_id=3,   # Court Circle (Index 2)
            initial_passenger_gps={'latitude': 15.344400, 'longitude': 75.145200, 'speed': 0.0}
        )
        self.assertEqual(short_engine.pickup_index, 0)
        self.assertEqual(short_engine.destination_index, 2)

        # Start trip
        short_engine.update_driver_gps(15.344400, 75.145200, speed=1.0)
        short_engine.update_passenger_gps(15.344630, 75.145200, speed=22.0)
        short_engine.update_driver_gps(15.344635, 75.145200, speed=22.0)
        self.assertEqual(short_engine.state, TripState.BOARDED_TRIP_ACTIVE)

        # Reach Stop 1 (Corporation Circle: 15.351400, 75.141800)
        short_engine.update_driver_gps(15.351400, 75.141800, speed=4.0)
        # Departing Stop 1 -> 1 stop away from Court Circle (Countdown 1 must trigger!)
        countdown_1 = [a for a in short_engine.announcements_history if a['type'] == 'COUNTDOWN_1_STOP']
        self.assertEqual(len(countdown_1), 1)
        self.assertIn("Court Circle", countdown_1[0]['message'])

        # Reach Stop 2 (Destination)
        short_engine.update_driver_gps(15.352405, 75.139105, speed=5.0)
        self.assertEqual(short_engine.state, TripState.COMPLETED)

    def test_invalid_stop_order_raises(self):
        """Pickup must precede destination stop in route sequence."""
        with self.assertRaises(ValueError):
            TripLifecycleEngine(
                route_stops=self.route_stops,
                pickup_stop_id=6,        # Raj Nagar (Index 5)
                destination_stop_id=1    # CBT (Index 0)
            )

    def test_lifecycle_evaluate_api(self):
        """Verify REST API endpoint /api/trip/lifecycle/evaluate/ returns lifecycle events."""
        from rest_framework.test import APIClient
        client = APIClient()

        # Step 1: Approaching pickup (125m)
        resp = client.post('/api/trip/lifecycle/evaluate/', {
            'route_stops': self.route_stops,
            'pickup_stop_id': 1,
            'destination_stop_id': 6,
            'passenger_gps': {'latitude': 15.344400, 'longitude': 75.145200, 'speed': 0.0},
            'driver_gps': {'latitude': 15.345500, 'longitude': 75.145200, 'speed': 22.0},
            'current_state': 'WAITING_FOR_BUS'
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data['state'], 'BUS_ARRIVING')
        self.assertTrue(len(data['events']) > 0)
        self.assertEqual(data['events'][0]['type'], 'PRE_BOARDING_APPROACHING')
        self.assertIn("arriving at your stop shortly", data['events'][0]['text'])

