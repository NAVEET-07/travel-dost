import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any, Set

logger = logging.getLogger(__name__)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two decimal degree points in meters.
    Uses mean Earth radius of 6,371,000 meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class TripState:
    WAITING_FOR_BUS = "WAITING_FOR_BUS"
    PRE_BOARDING_COUNTDOWN = "PRE_BOARDING_COUNTDOWN"
    BUS_ARRIVING = "BUS_ARRIVING"
    BOARDED_TRIP_ACTIVE = "BOARDED_TRIP_ACTIVE"
    BOARDED_IN_TRANSIT = "BOARDED_IN_TRANSIT"
    APPROACHING_DESTINATION = "APPROACHING_DESTINATION"
    ARRIVED_DESTINATION = "ARRIVED_DESTINATION"
    COMPLETED = "COMPLETED"


class TripLifecycleEngine:
    """
    Event-driven Trip Lifecycle & Proximity Announcer Engine.
    
    Manages:
    1. Pre-boarding proximity detection & upstream stop countdowns (3 stops, 2 stops, 1 stop, 100m, <20m arrived).
    2. Automatic trip start verification (Driver & Passenger within 25-30m, speed > 10 km/h).
    3. En-route dynamic stop progression & departure announcements.
    4. Relative destination countdown (3 stops, 2 stops, 1 stop away).
    5. Destination arrival (<20m) & trip completion.
    
    Includes threshold hysteresis buffers to eliminate GPS jitter notification spam.
    """

    # Proximity & Hysteresis Thresholds (meters & km/h)
    PRE_BOARDING_APPROACH_MIN = 50.0
    PRE_BOARDING_APPROACH_MAX = 150.0
    PRE_BOARDING_IMMINENT_MIN = 30.0
    PRE_BOARDING_IMMINENT_MAX = 50.0
    PRE_BOARDING_ARRIVED_DIST = 20.0
    PRE_BOARDING_MAX_SPEED = 6.0  # km/h (near zero speed)

    BOARDING_SYNC_RADIUS = 30.0    # meters between driver and passenger GPS (<= 25m nominal)
    BOARDING_MIN_SPEED = 10.0      # km/h moving away from pickup point

    INTERMEDIATE_APPROACH_RADIUS = 100.0  # meters
    INTERMEDIATE_CLEAR_RADIUS = 25.0      # meters to recognize stop passed

    DESTINATION_ARRIVAL_RADIUS = 20.0     # meters to final destination stop

    HYSTERESIS_BUFFER = 5.0  # meters buffer against GPS jitter oscillation

    def __init__(
        self,
        route_stops: List[Dict[str, Any]],
        pickup_stop_id: Any,
        destination_stop_id: Any,
        initial_passenger_gps: Optional[Dict[str, float]] = None,
        bus_number: Optional[str] = "42",
        on_announcement: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        on_state_change: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
    ):
        """
        :param route_stops: Ordered list of route stops: [{'id': 1, 'name': 'Stop A', 'lat': 15.3, 'lng': 75.1}, ...]
        :param pickup_stop_id: ID of passenger's boarding / pickup stop
        :param destination_stop_id: ID of passenger's destination stop
        :param initial_passenger_gps: {'latitude': float, 'longitude': float}
        :param bus_number: Bus number identifier for announcements
        :param on_announcement: Callback func(message, announcement_type, metadata)
        :param on_state_change: Callback func(old_state, new_state, metadata)
        """
        self.route_stops = list(route_stops)
        self.bus_number = str(bus_number or "42")
        self.on_announcement = on_announcement
        self.on_state_change = on_state_change


        self.pickup_stop = self._find_stop_by_id(pickup_stop_id)
        self.destination_stop = self._find_stop_by_id(destination_stop_id)

        if not self.pickup_stop:
            raise ValueError(f"Pickup stop ID '{pickup_stop_id}' not found in route stops.")
        if not self.destination_stop:
            raise ValueError(f"Destination stop ID '{destination_stop_id}' not found in route stops.")

        self.pickup_index = self.route_stops.index(self.pickup_stop)
        self.destination_index = self.route_stops.index(self.destination_stop)

        if self.pickup_index >= self.destination_index:
            raise ValueError("Pickup stop must precede destination stop in route sequence.")

        self.state = TripState.WAITING_FOR_BUS

        # Active telemetry state
        self.driver_gps: Optional[Dict[str, Any]] = None
        self.passenger_gps: Optional[Dict[str, Any]] = initial_passenger_gps or {
            'latitude': float(self.pickup_stop['lat']),
            'longitude': float(self.pickup_stop['lng']),
            'speed': 0.0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Dynamic stop tracking
        self.current_stop_index = self.pickup_index
        self.next_stop_index = self.pickup_index + 1

        # Hysteresis and de-duplication registry
        self._triggered_events: Set[str] = set()
        self._visited_stops: Set[Any] = set()
        self._last_evaluated_distance: Optional[float] = None
        self.announcements_history: List[Dict[str, Any]] = []

    def _find_stop_by_id(self, stop_id: Any) -> Optional[Dict[str, Any]]:
        for st in self.route_stops:
            if str(st.get('id')) == str(stop_id) or str(st.get('stop_id')) == str(stop_id):
                return st
        return None

    def _transition_to(self, new_state: str, metadata: Optional[Dict[str, Any]] = None):
        if self.state == new_state:
            return
        old_state = self.state
        self.state = new_state
        meta = metadata or {}
        meta.update({
            'old_state': old_state,
            'new_state': new_state,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"[TripLifecycle] State transition: {old_state} -> {new_state}")
        if self.on_state_change:
            try:
                self.on_state_change(old_state, new_state, meta)
            except Exception as e:
                logger.error(f"[TripLifecycle] Error in on_state_change callback: {e}")

    def _trigger_announcement(self, event_id: str, message: str, announcement_type: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Triggers announcement only if event_id has not already been fired,
        guaranteeing zero notification spam.
        """
        if event_id in self._triggered_events:
            return

        self._triggered_events.add(event_id)
        record = {
            'event_id': event_id,
            'message': message,
            'type': announcement_type,
            'state': self.state,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata or {}
        }
        self.announcements_history.append(record)
        logger.info(f"[TripLifecycle Announcement] [{announcement_type}] {message}")

        if self.on_announcement:
            try:
                self.on_announcement(message, announcement_type, record)
            except Exception as e:
                logger.error(f"[TripLifecycle] Error in on_announcement callback: {e}")

    def update_passenger_gps(self, latitude: float, longitude: float, speed: float = 0.0, timestamp: Optional[Any] = None):
        """Ingests continuous passenger GPS location."""
        self.passenger_gps = {
            'latitude': float(latitude),
            'longitude': float(longitude),
            'speed': float(speed or 0.0),
            'timestamp': str(timestamp or datetime.now(timezone.utc).isoformat())
        }

    def update_driver_gps(self, latitude: float, longitude: float, speed: float = 0.0, heading: float = 0.0, timestamp: Optional[Any] = None) -> Dict[str, Any]:
        """
        Primary continuous GPS ingestion hook.
        Evaluates state transitions, geofencing, stop progression, and proximity alerts.
        """
        lat = float(latitude)
        lon = float(longitude)
        spd = float(speed or 0.0)
        hdg = float(heading or 0.0)

        self.driver_gps = {
            'latitude': lat,
            'longitude': lon,
            'speed': spd,
            'heading': hdg,
            'timestamp': str(timestamp or datetime.now(timezone.utc).isoformat())
        }

        if self.state in [TripState.COMPLETED]:
            return self.get_status_snapshot()

        # -------------------------------------------------------------
        # 1. PRE-BOARDING & PROXIMITY DETECTION (Passenger at Pickup Stop)
        # -------------------------------------------------------------
        if self.state in [TripState.WAITING_FOR_BUS, TripState.PRE_BOARDING_COUNTDOWN, TripState.BUS_ARRIVING]:
            pickup_lat = float(self.pickup_stop['lat'])
            pickup_lng = float(self.pickup_stop['lng'])
            dist_to_pickup = haversine_distance_meters(lat, lon, pickup_lat, pickup_lng)

            # Upstream pre-boarding stop countdown
            if self.pickup_index > 0:
                closest_pre_idx = -1
                min_pre_dist = float('inf')
                for i in range(self.pickup_index):
                    st = self.route_stops[i]
                    d = haversine_distance_meters(lat, lon, float(st['lat']), float(st['lng']))
                    if d < min_pre_dist:
                        min_pre_dist = d
                        closest_pre_idx = i

                if closest_pre_idx != -1 and min_pre_dist <= 120.0:
                    stops_away = self.pickup_index - closest_pre_idx
                    if stops_away == 3:
                        if self.state != TripState.PRE_BOARDING_COUNTDOWN:
                            self._transition_to(TripState.PRE_BOARDING_COUNTDOWN, {'stops_away': 3})
                        self._trigger_announcement(
                            "countdown_preboard_3",
                            "Bus is 3 stops away from your pickup point.",
                            "COUNTDOWN_PREBOARD_3",
                            {'stops_away': 3, 'current_stop_index': closest_pre_idx}
                        )
                    elif stops_away == 2:
                        if self.state != TripState.PRE_BOARDING_COUNTDOWN:
                            self._transition_to(TripState.PRE_BOARDING_COUNTDOWN, {'stops_away': 2})
                        self._trigger_announcement(
                            "countdown_preboard_2",
                            "Bus is 2 stops away.",
                            "COUNTDOWN_PREBOARD_2",
                            {'stops_away': 2, 'current_stop_index': closest_pre_idx}
                        )
                    elif stops_away == 1:
                        if self.state != TripState.PRE_BOARDING_COUNTDOWN:
                            self._transition_to(TripState.PRE_BOARDING_COUNTDOWN, {'stops_away': 1})
                        self._trigger_announcement(
                            "countdown_preboard_1",
                            "Bus is at the previous stop. Arriving next at your location.",
                            "COUNTDOWN_PREBOARD_1",
                            {'stops_away': 1, 'current_stop_index': closest_pre_idx}
                        )

            # Approaching alert (100m - 150m)
            if dist_to_pickup <= (self.PRE_BOARDING_APPROACH_MAX + self.HYSTERESIS_BUFFER) and dist_to_pickup >= (self.PRE_BOARDING_APPROACH_MIN - self.HYSTERESIS_BUFFER):
                if self.state != TripState.BUS_ARRIVING:
                    self._transition_to(TripState.BUS_ARRIVING, {'distance_to_pickup': dist_to_pickup})
                self._trigger_announcement(
                    "preboarding_approaching",
                    "The bus is arriving at your stop shortly.",
                    "PRE_BOARDING_APPROACHING",
                    {'distance_meters': round(dist_to_pickup, 1), 'stop_name': self.pickup_stop['name']}
                )

            # Imminent alert (30m - 50m)
            if dist_to_pickup <= (self.PRE_BOARDING_IMMINENT_MAX + self.HYSTERESIS_BUFFER) and dist_to_pickup >= (self.PRE_BOARDING_IMMINENT_MIN - self.HYSTERESIS_BUFFER):
                if self.state != TripState.BUS_ARRIVING:
                    self._transition_to(TripState.BUS_ARRIVING, {'distance_to_pickup': dist_to_pickup})
                self._trigger_announcement(
                    "preboarding_imminent",
                    "The bus is within 50 meters of your stop. Please be ready.",
                    "PRE_BOARDING_IMMINENT",
                    {'distance_meters': round(dist_to_pickup, 1), 'stop_name': self.pickup_stop['name']}
                )

            # Arrived / Boarding alert (< 20m & speed near 0)
            if dist_to_pickup <= self.PRE_BOARDING_ARRIVED_DIST and spd <= self.PRE_BOARDING_MAX_SPEED:
                self._trigger_announcement(
                    "preboarding_arrived",
                    "The bus has arrived at your stop. Please board the bus.",
                    "PRE_BOARDING_ARRIVED",
                    {'distance_meters': round(dist_to_pickup, 1), 'speed_kmh': spd, 'stop_name': self.pickup_stop['name'], 'bus_number': self.bus_number}
                )

            # ---------------------------------------------------------
            # 2. AUTOMATIC TRIP START (Driver & Passenger Sync)
            # ---------------------------------------------------------
            if self.passenger_gps:
                p_lat = float(self.passenger_gps['latitude'])
                p_lng = float(self.passenger_gps['longitude'])
                passenger_driver_dist = haversine_distance_meters(lat, lon, p_lat, p_lng)
                dist_away_from_pickup = haversine_distance_meters(lat, lon, pickup_lat, pickup_lng)

                # Sync check: driver and passenger within 30m radius AND bus begins moving (speed > 10 km/h away from pickup point)
                if passenger_driver_dist <= self.BOARDING_SYNC_RADIUS and spd >= self.BOARDING_MIN_SPEED and dist_away_from_pickup >= 20.0:
                    dest_name = self.destination_stop['name']
                    self._transition_to(TripState.BOARDED_TRIP_ACTIVE, {
                        'passenger_driver_dist': passenger_driver_dist,
                        'speed': spd,
                        'dist_away_from_pickup': dist_away_from_pickup
                    })
                    self._trigger_announcement(
                        "trip_started",
                        f"Trip started. Welcome aboard! You are now aboard Bus #{self.bus_number}. Enjoy your trip! Tracking your journey to {dest_name}.",
                        "TRIP_STARTED",
                        {'destination_name': dest_name, 'speed_kmh': spd, 'bus_number': self.bus_number}
                    )
                    self._visited_stops.add(self.pickup_stop.get('id', self.pickup_index))
                    self._announce_departure_to_next_stop()

        # -------------------------------------------------------------
        # 3. EN-ROUTE DYNAMIC STOP PROGRESSION & RELATIVE COUNTDOWN
        # -------------------------------------------------------------
        elif self.state in [TripState.BOARDED_TRIP_ACTIVE, TripState.BOARDED_IN_TRANSIT, TripState.APPROACHING_DESTINATION]:
            self._evaluate_en_route_progression(lat, lon, spd)

        return self.get_status_snapshot()


    def _evaluate_en_route_progression(self, lat: float, lon: float, spd: float):
        """Monitors intermediate stops, destination countdowns, and arrival."""
        dest_lat = float(self.destination_stop['lat'])
        dest_lng = float(self.destination_stop['lng'])
        dist_to_final_dest = haversine_distance_meters(lat, lon, dest_lat, dest_lng)

        # -------------------------------------------------------------
        # 5. FINAL DESTINATION ARRIVAL (< 20m)
        # -------------------------------------------------------------
        if dist_to_final_dest <= self.DESTINATION_ARRIVAL_RADIUS:
            dest_name = self.destination_stop['name']
            self._transition_to(TripState.ARRIVED_DESTINATION, {'distance_to_dest': dist_to_final_dest})
            self._trigger_announcement(
                "destination_arrived",
                f"You have arrived at your destination: {dest_name}. Please safely exit the bus.",
                "DESTINATION_ARRIVED",
                {'destination_name': dest_name, 'distance_meters': round(dist_to_final_dest, 1)}
            )
            self._transition_to(TripState.COMPLETED, {'completed_at': datetime.now(timezone.utc).isoformat()})
            return

        # Check next stop along route
        if self.next_stop_index < len(self.route_stops):
            target_stop = self.route_stops[self.next_stop_index]
            target_lat = float(target_stop['lat'])
            target_lng = float(target_stop['lng'])
            dist_to_target = haversine_distance_meters(lat, lon, target_lat, target_lng)

            target_id = target_stop.get('id', self.next_stop_index)
            approach_event_key = f"approaching_stop_{target_id}"

            # Approaching intermediate stop (within 100m)
            if dist_to_target <= self.INTERMEDIATE_APPROACH_RADIUS:
                if target_id not in self._visited_stops:
                    self._trigger_announcement(
                        approach_event_key,
                        f"Approaching stop: {target_stop['name']}.",
                        "STOP_APPROACHING",
                        {'stop_name': target_stop['name'], 'distance_meters': round(dist_to_target, 1)}
                    )

            # Cleared stop geofence: bus reached close proximity or passed beyond
            if dist_to_target <= self.INTERMEDIATE_CLEAR_RADIUS or (
                approach_event_key in self._triggered_events and dist_to_target > self.INTERMEDIATE_CLEAR_RADIUS and spd > 10.0
            ):
                if target_id not in self._visited_stops:
                    self._visited_stops.add(target_id)
                    self.current_stop_index = self.next_stop_index
                    self.next_stop_index += 1

                    # Departed stop -> Announce next stop & check relative countdown
                    self._announce_departure_to_next_stop()
                    self._check_relative_destination_countdown()

    def _announce_departure_to_next_stop(self):
        """Announces: 'Next stop is: [Next Stop Name]' upon departure."""
        if self.next_stop_index < len(self.route_stops):
            next_stop = self.route_stops[self.next_stop_index]
            next_id = next_stop.get('id', self.next_stop_index)
            self._trigger_announcement(
                f"departed_for_stop_{next_id}",
                f"Next stop is: {next_stop['name']}.",
                "NEXT_STOP_ANNOUNCEMENT",
                {'next_stop_name': next_stop['name'], 'next_stop_order': self.next_stop_index}
            )

    def _check_relative_destination_countdown(self):
        """
        4. Relative Destination Countdown (Last 3 Stops):
        stops_remaining = passenger_destination_index - current_stop_index
        """
        stops_remaining = self.destination_index - self.current_stop_index
        dest_name = self.destination_stop['name']

        if stops_remaining == 3:
            if self.state == TripState.BOARDED_TRIP_ACTIVE:
                self._transition_to(TripState.APPROACHING_DESTINATION, {'stops_remaining': 3})
            self._trigger_announcement(
                "countdown_3_stops",
                f"Notice: Your destination {dest_name} is approaching in 3 stops.",
                "COUNTDOWN_3_STOPS",
                {'stops_remaining': 3, 'destination_name': dest_name}
            )

        elif stops_remaining == 2:
            if self.state == TripState.BOARDED_TRIP_ACTIVE:
                self._transition_to(TripState.APPROACHING_DESTINATION, {'stops_remaining': 2})
            self._trigger_announcement(
                "countdown_2_stops",
                f"Your destination is approaching after the next stop (2 stops away).",
                "COUNTDOWN_2_STOPS",
                {'stops_remaining': 2, 'destination_name': dest_name}
            )

        elif stops_remaining == 1:
            if self.state in [TripState.BOARDED_TRIP_ACTIVE, TripState.APPROACHING_DESTINATION]:
                self._transition_to(TripState.APPROACHING_DESTINATION, {'stops_remaining': 1})
            self._trigger_announcement(
                "countdown_1_stop",
                f"Next stop is your destination: {dest_name}. Please prepare your belongings.",
                "COUNTDOWN_1_STOP",
                {'stops_remaining': 1, 'destination_name': dest_name}
            )

    def get_status_snapshot(self) -> Dict[str, Any]:
        """Provides complete real-time status snapshot of the trip."""
        dist_pickup = None
        dist_dest = None
        dist_next = None

        if self.driver_gps:
            d_lat = self.driver_gps['latitude']
            d_lon = self.driver_gps['longitude']
            dist_pickup = round(haversine_distance_meters(d_lat, d_lon, float(self.pickup_stop['lat']), float(self.pickup_stop['lng'])), 1)
            dist_dest = round(haversine_distance_meters(d_lat, d_lon, float(self.destination_stop['lat']), float(self.destination_stop['lng'])), 1)

            if self.next_stop_index < len(self.route_stops):
                n_stop = self.route_stops[self.next_stop_index]
                dist_next = round(haversine_distance_meters(d_lat, d_lon, float(n_stop['lat']), float(n_stop['lng'])), 1)

        stops_remaining = max(0, self.destination_index - self.current_stop_index)
        next_stop_obj = self.route_stops[self.next_stop_index] if self.next_stop_index < len(self.route_stops) else None

        return {
            'state': self.state,
            'pickup_stop': self.pickup_stop['name'],
            'destination_stop': self.destination_stop['name'],
            'current_stop': self.route_stops[self.current_stop_index]['name'] if self.current_stop_index < len(self.route_stops) else None,
            'next_stop': next_stop_obj['name'] if next_stop_obj else None,
            'next_stop_index': self.next_stop_index,
            'stops_remaining': stops_remaining,
            'distance_to_pickup_meters': dist_pickup,
            'distance_to_destination_meters': dist_dest,
            'distance_to_next_stop_meters': dist_next,
            'driver_gps': self.driver_gps,
            'passenger_gps': self.passenger_gps,
            'total_announcements_count': len(self.announcements_history),
            'latest_announcement': self.announcements_history[-1] if self.announcements_history else None,
            'is_completed': self.state == TripState.COMPLETED
        }
