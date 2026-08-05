import urllib.request
import urllib.error
import json
import math
import logging

logger = logging.getLogger(__name__)

def generate_haversine_waypoints(p1, p2, num_steps=5):
    """Fallback generator for intermediate waypoints between two points."""
    lat1, lon1 = p1
    lat2, lon2 = p2
    points = []
    for i in range(num_steps + 1):
        ratio = i / float(num_steps)
        lat = lat1 + (lat2 - lat1) * ratio
        lon = lon1 + (lon2 - lon1) * ratio
        points.append([round(lat, 6), round(lon, 6)])
    return points

def fetch_osrm_road_geometry(stop_coordinates):
    """
    Fetch road-aligned geometry from OSRM public API given a list of [lat, lng] stop coordinates.
    OSRM expects lon,lat;lon,lat format.
    Returns a list of [lat, lng] points following actual roads.
    """
    if len(stop_coordinates) < 2:
        return stop_coordinates

    # Format waypoints for OSRM API (lng,lat)
    coord_strs = [f"{lng:.6f},{lat:.6f}" for lat, lng in stop_coordinates]
    
    # OSRM limits URL length, so chunk if there are many stops (>25)
    chunk_size = 20
    all_road_points = []
    
    for i in range(0, len(coord_strs) - 1, chunk_size - 1):
        chunk = coord_strs[i:i + chunk_size]
        if len(chunk) < 2:
            continue
            
        url = f"https://router.project-osrm.org/route/v1/driving/{';'.join(chunk)}?overview=full&geometries=geojson"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'TravelDost/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if data.get('code') == 'Ok' and data.get('routes'):
                        geojson_coords = data['routes'][0]['geometry']['coordinates']
                        # OSRM GeoJSON gives [lng, lat], convert to [lat, lng]
                        chunk_points = [[coord[1], coord[0]] for coord in geojson_coords]
                        if all_road_points and chunk_points:
                            all_road_points.extend(chunk_points[1:])
                        else:
                            all_road_points.extend(chunk_points)
                        continue
        except Exception as e:
            logger.warning(f"OSRM request failed: {e}")

            
        # Fallback for this chunk if OSRM call failed
        sub_coords = stop_coordinates[i:i + chunk_size]
        chunk_points = []
        for j in range(len(sub_coords) - 1):
            pts = generate_haversine_waypoints(sub_coords[j], sub_coords[j+1])
            if chunk_points and pts:
                chunk_points.extend(pts[1:])
            else:
                chunk_points.extend(pts)
        if all_road_points and chunk_points:
            all_road_points.extend(chunk_points[1:])
        else:
            all_road_points.extend(chunk_points)

    return all_road_points if all_road_points else stop_coordinates


def get_or_generate_road_geometry(route, force_refresh=False):
    """
    Retrieves cached road geometry from route.shape_geometry or fetches road geometry from OSRM.
    """
    if not force_refresh and route.shape_geometry and len(route.shape_geometry) >= 2:
        return route.shape_geometry

    ordered_stops = list(route.get_ordered_stops())
    if len(ordered_stops) < 2:
        return []

    stop_coords = [[rs.bus_stop.latitude, rs.bus_stop.longitude] for rs in ordered_stops]
    
    # Try fetching OSRM road geometry
    road_points = fetch_osrm_road_geometry(stop_coords)
    
    if road_points and len(road_points) >= 2:
        route.shape_geometry = road_points
        try:
            route.save(update_fields=['shape_geometry'])
        except Exception:
            pass
        return road_points
        
    return stop_coords
