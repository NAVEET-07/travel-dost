import urllib.request
import urllib.error
import json
import math
import logging

logger = logging.getLogger(__name__)

# In-memory LRU-style segment cache for stop-to-stop road geometries
_SEGMENT_CACHE = {}

def generate_haversine_waypoints(p1, p2, num_steps=6):
    """Fallback generator for intermediate waypoints between two points."""
    lat1, lon1 = float(p1[0]), float(p1[1])
    lat2, lon2 = float(p2[0]), float(p2[1])
    points = []
    for i in range(num_steps + 1):
        ratio = i / float(num_steps)
        lat = lat1 + (lat2 - lat1) * ratio
        lon = lon1 + (lon2 - lon1) * ratio
        points.append([round(lat, 6), round(lon, 6)])
    return points


def fetch_single_segment_osrm(p1, p2):
    """
    Fetch exact road-aligned geometry between two consecutive stops using OSRM.
    Uses segment caching to avoid redundant HTTP requests.
    """
    lat1, lon1 = round(float(p1[0]), 5), round(float(p1[1]), 5)
    lat2, lon2 = round(float(p2[0]), 5), round(float(p2[1]), 5)

    if lat1 == lat2 and lon1 == lon2:
        return [[lat1, lon1]]

    cache_key = (lat1, lon1, lat2, lon2)
    if cache_key in _SEGMENT_CACHE:
        return _SEGMENT_CACHE[cache_key]

    url = f"https://router.project-osrm.org/route/v1/driving/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}?overview=full&geometries=geojson"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'TravelDost/1.0'})
        with urllib.request.urlopen(req, timeout=3.5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('code') == 'Ok' and data.get('routes'):
                    geojson_coords = data['routes'][0]['geometry']['coordinates']
                    # OSRM gives [lng, lat], convert to [lat, lng]
                    pts = [[coord[1], coord[0]] for coord in geojson_coords]
                    if len(pts) >= 2:
                        _SEGMENT_CACHE[cache_key] = pts
                        return pts
    except Exception as e:
        logger.debug(f"OSRM consecutive segment failed for {cache_key}: {e}")

    # Fallback to smooth linear waypoints for this consecutive segment
    fallback_pts = generate_haversine_waypoints([lat1, lon1], [lat2, lon2], num_steps=6)
    _SEGMENT_CACHE[cache_key] = fallback_pts
    return fallback_pts


def fetch_consecutive_stops_road_geometry(stop_coordinates):
    """
    Constructs complete route geometry by obtaining road-following geometry
    consecutively for every pair of consecutive stops: STOP[i] -> STOP[i+1].
    
    This strictly prevents multi-waypoint loop artifacts (e.g. entering airport
    interiors unnecessarily, U-turn detours) and cleanly joins segments without
    duplicate seam coordinates.
    """
    if not stop_coordinates or len(stop_coordinates) < 2:
        return stop_coordinates or []

    all_road_points = []

    for i in range(len(stop_coordinates) - 1):
        p1 = stop_coordinates[i]
        p2 = stop_coordinates[i + 1]

        segment_points = fetch_single_segment_osrm(p1, p2)

        if not all_road_points:
            all_road_points.extend(segment_points)
        else:
            # Skip the first coordinate of subsequent segments to avoid duplicate seam points
            all_road_points.extend(segment_points[1:])

    return all_road_points if all_road_points else stop_coordinates


def fetch_osrm_road_geometry(stop_coordinates):
    """
    Public entry point for road geometry generation.
    Enforces consecutive stop-to-stop road tracing according to Problem 4 requirements.
    """
    return fetch_consecutive_stops_road_geometry(stop_coordinates)


def get_or_generate_road_geometry(route, force_refresh=False):
    """
    Retrieves cached road geometry from route.shape_geometry or calculates
    consecutive stop-to-stop road geometry.
    """
    if not force_refresh and route.shape_geometry and len(route.shape_geometry) >= 2:
        return route.shape_geometry

    ordered_stops = list(route.get_ordered_stops())
    if len(ordered_stops) < 2:
        return []

    stop_coords = [[float(rs.bus_stop.latitude), float(rs.bus_stop.longitude)] for rs in ordered_stops]
    
    road_points = fetch_consecutive_stops_road_geometry(stop_coords)
    
    if road_points and len(road_points) >= 2:
        route.shape_geometry = road_points
        try:
            route.save(update_fields=['shape_geometry'])
        except Exception:
            pass
        return road_points
        
    return stop_coords
