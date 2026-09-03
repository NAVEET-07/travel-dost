import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    Returns distance in kilometers.
    """
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return round(distance, 3)

def calculate_heading(lat1, lon1, lat2, lon2):
    """
    Calculate compass heading angle in degrees (0..360) from point 1 to point 2.
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon_rad = math.radians(lon2 - lon1)

    y = math.sin(dlon_rad) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
    
    bearing = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing) + 360) % 360
    return round(bearing_deg, 1)

def validate_coordinates(lat, lon):
    if lat is None:
        return False, "Missing latitude coordinate."
    if lon is None:
        return False, "Missing longitude coordinate."
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return False, "Coordinates must be valid numbers."

    if not (-90.0 <= lat_f <= 90.0):
        return False, "Latitude out of range [-90, 90]."
    if not (-180.0 <= lon_f <= 180.0):
        return False, "Longitude out of range [-180, 180]."
    return True, None

def calculate_consecutive_stops_distance(stops):
    total = 0.0
    for i in range(len(stops) - 1):
        s1 = stops[i]
        s2 = stops[i+1]
        lat1 = s1.get('lat') if isinstance(s1, dict) else getattr(s1, 'latitude', 0.0)
        lon1 = s1.get('lng', s1.get('lon')) if isinstance(s1, dict) else getattr(s1, 'longitude', 0.0)
        lat2 = s2.get('lat') if isinstance(s2, dict) else getattr(s2, 'latitude', 0.0)
        lon2 = s2.get('lng', s2.get('lon')) if isinstance(s2, dict) else getattr(s2, 'longitude', 0.0)
        total += haversine_distance(lat1, lon1, lat2, lon2)
    return round(total, 2)

def calculate_walk_distance(p1, p2):
    lat1 = p1.get('lat') if isinstance(p1, dict) else getattr(p1, 'latitude', 0.0)
    lon1 = p1.get('lng', p1.get('lon')) if isinstance(p1, dict) else getattr(p1, 'longitude', 0.0)
    lat2 = p2.get('lat') if isinstance(p2, dict) else getattr(p2, 'latitude', 0.0)
    lon2 = p2.get('lng', p2.get('lon')) if isinstance(p2, dict) else getattr(p2, 'longitude', 0.0)
    dist_km = haversine_distance(lat1, lon1, lat2, lon2)
    return dist_km, format_distance(dist_km)

def format_distance(dist_km):
    if dist_km < 1.0:
        return f"{int(dist_km * 1000)} m"
    return f"{dist_km:.2f} km"

def audit_stop_coordinates_data():
    from tracking.models import BusStop
    stops = list(BusStop.objects.filter(is_active=True))
    total = len(stops)
    valid_count = 0
    suspicious_count = 0
    for s in stops:
        is_valid, _ = validate_coordinates(s.latitude, s.longitude)
        if is_valid:
            valid_count += 1
    return {
        "summary": {
            "total_stops": total,
            "valid_stops_count": valid_count,
            "suspicious_distances_count": suspicious_count
        }
    }
