"""
Travel Dost - NWKRTC City Bus Fare & Hubballi-Dharwad Travel Time Engine.

Calculates realistic fare structures and travel durations for city transit:
- Fare: Official NWKRTC distance-slab city bus tariffs.
- Travel Time: Takes into account base bus speed (~28 km/h), dwell time per intermediate stop (~0.6 min), and junction delays.
"""

def calculate_nwkrtc_fare(distance_km, bus_type='ORDINARY', is_multi_leg=False, leg_fares=None):
    """
    Calculates NWKRTC city bus fare based on cumulative road distance (in km).
    
    NWKRTC City Bus Distance Slab Tariff:
    - 0.0 - 2.0 km: ₹7.00
    - 2.1 - 4.0 km: ₹12.00
    - 4.1 - 6.0 km: ₹15.00
    - 6.1 - 8.0 km: ₹18.00
    - 8.1 - 12.0 km: ₹22.00
    - 12.1 - 16.0 km: ₹26.00
    - 16.1 - 20.0 km: ₹30.00
    - 20.1 - 25.0 km: ₹35.00
    - 25.1 - 30.0 km: ₹40.00
    - > 30.0 km: ₹45.00 + ₹1.50 per km above 30km
    """
    if leg_fares and len(leg_fares) > 0:
        return round(sum(leg_fares), 2)

    dist = float(distance_km)
    if dist <= 0:
        return 7.00

    if dist <= 2.0:
        base_fare = 7.00
    elif dist <= 4.0:
        base_fare = 12.00
    elif dist <= 6.0:
        base_fare = 15.00
    elif dist <= 8.0:
        base_fare = 18.00
    elif dist <= 12.0:
        base_fare = 22.00
    elif dist <= 16.0:
        base_fare = 26.00
    elif dist <= 20.0:
        base_fare = 30.00
    elif dist <= 25.0:
        base_fare = 35.00
    elif dist <= 30.0:
        base_fare = 40.00
    else:
        base_fare = 45.00 + ((dist - 30.0) * 1.50)

    # Multiplier for Express or Chigari BRTS routes
    bus_type_upper = str(bus_type).upper()
    if 'BRTS' in bus_type_upper or 'CHIGARI' in bus_type_upper:
        base_fare = base_fare * 1.25
    elif 'EXPRESS' in bus_type_upper:
        base_fare = base_fare * 1.15

    return round(max(7.00, base_fare), 2)


def calculate_travel_time(distance_km, stops_count, transfers=0, bus_type='ORDINARY'):
    """
    Calculates realistic Hubballi-Dharwad city bus travel time in minutes.
    
    Factors:
    - Average city bus speed: ~28 km/h for ordinary, ~35 km/h for BRTS/express.
    - Intermediate stop dwell time: ~0.6 mins (36 seconds) per stop.
    - Major junction delay buffer: ~1.5 mins per 5 km of travel.
    - Transfer penalty: ~5-10 mins per bus change for waiting/walking.
    """
    dist = float(distance_km)
    stops = int(stops_count)
    
    bus_type_upper = str(bus_type).upper()
    if 'BRTS' in bus_type_upper:
        avg_speed_kmh = 36.0
        dwell_per_stop_min = 0.4
    elif 'EXPRESS' in bus_type_upper:
        avg_speed_kmh = 32.0
        dwell_per_stop_min = 0.5
    else:
        avg_speed_kmh = 27.5
        dwell_per_stop_min = 0.65

    # Pure motion time in minutes
    motion_time_mins = (dist / avg_speed_kmh) * 60.0
    
    # Intermediate stop dwell time
    dwell_time_mins = max(0, stops - 1) * dwell_per_stop_min
    
    # Junction / traffic delay buffer
    junction_delays_mins = (dist / 5.0) * 1.2
    
    # Transfer wait penalty
    transfer_wait_mins = transfers * 6.0
    
    total_mins = motion_time_mins + dwell_time_mins + junction_delays_mins + transfer_wait_mins
    
    return max(4, int(round(total_mins)))
