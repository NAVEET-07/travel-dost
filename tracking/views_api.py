from rest_framework import status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser, BasePermission
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone

from tracking.models import User, BusStop, Route, RouteStop, Bus, GPSDevice, BusLocation, Fare, BusTrackingSession, SearchHistory
from tracking.serializers import (
    UserSerializer, BusStopSerializer, RouteSerializer, BusSerializer,
    GPSDeviceSerializer, BusLocationSerializer, FareSerializer,
    BusTrackingSessionSerializer, SearchHistorySerializer, RouteStopSerializer
)
from tracking.services.distance import haversine_distance
from tracking.services.route_finder import find_best_routes, resolve_bus_stop
from tracking.services.road_geometry import get_or_generate_road_geometry


class IsAdminRoleOrStaff(BasePermission):

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin()


# -------------------------------------------------------------------
# AUTHENTICATION APIS
# -------------------------------------------------------------------
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User registered successfully.",
                "user": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            # Automatically route user to their role-specific dashboard
            if user.is_admin():
                redirect_url = '/admin/dashboard/'
            elif user.is_driver():
                redirect_url = '/driver/dashboard/'
            else:
                redirect_url = '/dashboard/'

            return Response({
                "message": "Login successful.",
                "redirect_url": redirect_url,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "is_staff": user.is_staff
                }
            })
        return Response({"error": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutAPIView(APIView):
    def post(self, request):
        logout(request)
        return Response({"message": "Logout successful."})


# -------------------------------------------------------------------
# BUS, ROUTE & STOP VIEWSETS
# -------------------------------------------------------------------
class BusViewSet(viewsets.ModelViewSet):
    queryset = Bus.objects.all()
    serializer_class = BusSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminRoleOrStaff()]


class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminRoleOrStaff()]


class BusStopViewSet(viewsets.ModelViewSet):
    queryset = BusStop.objects.all()
    serializer_class = BusStopSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'autocomplete', 'names']:
            return [AllowAny()]
        return [IsAdminRoleOrStaff()]

    @action(detail=False, methods=['get'])
    def autocomplete(self, request):
        stops = list(BusStop.objects.filter(is_active=True).values_list('stop_name', flat=True).distinct().order_by('stop_name'))
        return Response({"stops": stops})

    @action(detail=False, methods=['get'])
    def names(self, request):
        stops = list(BusStop.objects.filter(is_active=True).values_list('stop_name', flat=True).distinct().order_by('stop_name'))
        return Response({"stops": stops})


class FareViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Fare.objects.all()
    serializer_class = FareSerializer
    permission_classes = [AllowAny]


class GPSDeviceViewSet(viewsets.ModelViewSet):
    queryset = GPSDevice.objects.all()
    serializer_class = GPSDeviceSerializer
    permission_classes = [IsAdminRoleOrStaff]


# -------------------------------------------------------------------
# DYNAMIC ROUTE STOPS MANAGEMENT APIS
# -------------------------------------------------------------------
class AddRouteStopAPIView(APIView):
    permission_classes = [IsAdminRoleOrStaff]

    def post(self, request, pk):
        route = generics.get_object_or_404(Route, pk=pk)
        bus_stop_id = request.data.get('bus_stop_id')
        stop_order = request.data.get('stop_order')
        distance = request.data.get('distance_from_start_km', 0.0)

        if not bus_stop_id:
            return Response({"error": "bus_stop_id is required."}, status=400)

        bus_stop = generics.get_object_or_404(BusStop, pk=bus_stop_id)

        if not stop_order:
            stop_order = RouteStop.objects.filter(route=route).count() + 1

        route_stop, created = RouteStop.objects.update_or_create(
            route=route,
            stop_order=stop_order,
            defaults={
                'bus_stop': bus_stop,
                'distance_from_start_km': float(distance)
            }
        )

        return Response({
            "message": "Stop added to route successfully.",
            "route_stop": RouteStopSerializer(route_stop).data
        }, status=status.HTTP_201_CREATED)


class DeleteRouteStopAPIView(APIView):
    permission_classes = [IsAdminRoleOrStaff]

    def delete(self, request, pk):
        route_stop = generics.get_object_or_404(RouteStop, pk=pk)
        route_stop.delete()
        return Response({"message": "Route stop deleted successfully."})


# -------------------------------------------------------------------
# FEATURE SPECIFIC APIS
# -------------------------------------------------------------------
class StopsAutocompleteAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        stops = list(BusStop.objects.filter(is_active=True).values_list('stop_name', flat=True).distinct().order_by('stop_name'))
        return Response({"stops": stops})


class RouteSearchAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        source_id = request.query_params.get('source')
        dest_id = request.query_params.get('destination')

        if not source_id or not dest_id:
            return Response({
                "status": "error",
                "message": "Both 'source' and 'destination' query params are required.",
                "error": "Both 'source' and 'destination' query params are required."
            }, status=400)

        # Log search history if user is authenticated
        source_stop = BusStop.objects.filter(id=source_id).first() if str(source_id).isdigit() else resolve_bus_stop(source_id)
        dest_stop = BusStop.objects.filter(id=dest_id).first() if str(dest_id).isdigit() else resolve_bus_stop(dest_id)
        if source_stop and dest_stop:
            SearchHistory.objects.create(
                user=request.user if request.user.is_authenticated else None,
                source_stop_name=source_stop.stop_name,
                destination_stop_name=dest_stop.stop_name
            )

        results = find_best_routes(source_id, dest_id)
        if "error" in results:
            return Response({
                "status": "error",
                "message": results["error"],
                "error": results["error"],
                "total_options": 0,
                "top_routes": [],
                "routes": [],
                "total_routes_found": 0
            })

        top_routes = []
        for r in results.get("routes", []):
            legs_data = []
            raw_legs = r.get("legs", [])
            if not raw_legs:
                seg1 = r.get("segment_1", {})
                stops_list = seg1.get("stops", [])
                path_names = [st.get("name", "") for st in stops_list]
                path_coords = [{
                    "stop_name": st.get("name", ""),
                    "lat": float(st.get("lat", 0.0) or 0.0),
                    "lon": float(st.get("lng", st.get("lon", 0.0)) or 0.0),
                    "lng": float(st.get("lng", st.get("lon", 0.0)) or 0.0)
                } for st in stops_list]
                legs_data.append({
                    "bus_no": r.get("buses", [{}])[0].get("bus_number") if r.get("buses") else r.get("route_name", "Direct"),
                    "board_at": seg1.get("board_at", results.get("source", {}).get("name", "")),
                    "alight_at": seg1.get("alight_at", results.get("destination", {}).get("name", "")),
                    "stops_in_leg": len(stops_list),
                    "path_names": path_names,
                    "path_coords": path_coords
                })
            else:
                for idx, leg in enumerate(raw_legs):
                    leg_stops = leg.get("stops", [])
                    path_names = [st.get("name", "") for st in leg_stops]
                    path_coords = [{
                        "stop_name": st.get("name", ""),
                        "lat": float(st.get("lat", 0.0) or 0.0),
                        "lon": float(st.get("lng", st.get("lon", 0.0)) or 0.0),
                        "lng": float(st.get("lng", st.get("lon", 0.0)) or 0.0)
                    } for st in leg_stops]
                    leg_bus_no = leg.get("buses", [{}])[0].get("bus_number") if leg.get("buses") else leg.get("route_name", f"Leg {idx+1}")
                    legs_data.append({
                        "bus_no": leg_bus_no,
                        "board_at": leg.get("from_stop", ""),
                        "alight_at": leg.get("to_stop", ""),
                        "stops_in_leg": len(leg_stops),
                        "path_names": path_names,
                        "path_coords": path_coords
                    })

            transfers = r.get("transfers", 0)
            transfer_label = "Direct" if transfers == 0 else (f"{transfers} Transfer" if transfers == 1 else f"{transfers} Transfers")
            total_stops = r.get("stop_count", sum(len(l.get("stops", [])) for l in raw_legs))

            route_item = dict(r)
            route_item.update({
                "transfers": transfers,
                "transfer_label": transfer_label,
                "total_stops": total_stops,
                "legs": legs_data
            })
            top_routes.append(route_item)

        source_name = results.get("source", {}).get("name", str(source_id)) if isinstance(results.get("source"), dict) else str(results.get("source", source_id))
        dest_name = results.get("destination", {}).get("name", str(dest_id)) if isinstance(results.get("destination"), dict) else str(results.get("destination", dest_id))

        formatted_response = {
            "status": "success",
            "source": source_name,
            "destination": dest_name,
            "total_options": len(top_routes),
            "top_routes": top_routes,
            "total_routes_found": results.get("total_routes_found", len(top_routes)),
            "routes": results.get("routes", [])
        }
        return Response(formatted_response)


class NearbyStopsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
            limit = int(request.query_params.get('limit', 5))
        except (TypeError, ValueError):
            return Response({"error": "Valid 'lat' and 'lng' float parameters are required."}, status=400)

        stops = BusStop.objects.filter(is_active=True)
        stops_with_distance = []

        for stop in stops:
            dist = haversine_distance(lat, lng, stop.latitude, stop.longitude)
            stops_with_distance.append({
                "id": stop.id,
                "stop_name": stop.stop_name,
                "area": stop.area,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
                "description": stop.description,
                "distance_km": dist,
                "distance_meters": int(dist * 1000)
            })

        stops_with_distance.sort(key=lambda x: x['distance_km'])
        return Response({
            "user_location": {"lat": lat, "lng": lng},
            "total_stops": len(stops_with_distance),
            "nearby_stops": stops_with_distance[:limit]
        })


class BusLocationAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            bus = Bus.objects.get(pk=pk)
            loc = bus.get_current_location()
            if loc:
                return Response(BusLocationSerializer(loc).data)
            return Response({"message": "No location records available for this bus yet.", "bus_id": bus.id}, status=404)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=404)

    def post(self, request, pk):
        # REST endpoint for GPS device location submission
        try:
            bus = Bus.objects.get(pk=pk)
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=404)

        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        speed = request.data.get('speed', 0.0)
        heading = request.data.get('heading', 0.0)
        status_val = request.data.get('status', 'LIVE')

        if lat is None or lng is None:
            return Response({"error": "'latitude' and 'longitude' fields are required."}, status=400)

        bus.tracking_status = status_val
        bus.last_updated = timezone.now()
        bus.save(update_fields=['tracking_status', 'last_updated'])

        location = BusLocation.objects.create(
            bus=bus,
            latitude=float(lat),
            longitude=float(lng),
            speed=float(speed),
            heading=float(heading)
        )

        # Broadcast update to WebSockets via Channel Layer
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                payload = {
                    'type': 'bus_location_broadcast',
                    'bus_id': bus.id,
                    'bus_number': bus.bus_number,
                    'bus_name': bus.bus_name,
                    'bus_type': bus.get_bus_type_display(),
                    'latitude': float(lat),
                    'longitude': float(lng),
                    'speed': float(speed),
                    'heading': float(heading),
                    'status': status_val,
                    'timestamp': location.timestamp.isoformat()
                }
                async_to_sync(channel_layer.group_send)(f'bus_{bus.id}', payload)
                async_to_sync(channel_layer.group_send)('bus_all', payload)
        except Exception:
            pass

        return Response(BusLocationSerializer(location).data, status=status.HTTP_201_CREATED)


class BusTrackingStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            bus = Bus.objects.select_related('route').get(pk=pk)
            loc = bus.get_current_location()

            route_stops_data = []
            current_stop_data = None
            next_stop_data = None
            leg_a_to_c = []
            leg_c_to_f = []

            if bus.route:
                rs_list = list(bus.route.route_stops.select_related('bus_stop').order_by('stop_order'))
                route_stops_data = [
                    {
                        "id": rs.bus_stop.id,
                        "name": rs.bus_stop.stop_name,
                        "area": rs.bus_stop.area,
                        "lat": rs.bus_stop.latitude,
                        "lng": rs.bus_stop.longitude,
                        "stop_order": rs.stop_order,
                        "distance_km": rs.distance_from_start_km
                    }
                    for rs in rs_list
                ]

                if route_stops_data:
                    current_idx = 0
                    if loc and loc.latitude and loc.longitude:
                        # Find closest stop to bus's current GPS location
                        min_dist = float('inf')
                        for idx, st in enumerate(route_stops_data):
                            dist = haversine_distance(loc.latitude, loc.longitude, st['lat'], st['lng'])
                            if dist < min_dist:
                                min_dist = dist
                                current_idx = idx

                    current_stop_data = route_stops_data[current_idx]

                    if current_idx < len(route_stops_data) - 1:
                        next_stop_data = route_stops_data[current_idx + 1]
                        if loc and loc.latitude and loc.longitude:
                            dist_to_next = haversine_distance(
                                loc.latitude, loc.longitude,
                                next_stop_data['lat'], next_stop_data['lng']
                            )
                            next_stop_data['distance_km_to_next'] = round(dist_to_next, 2)
                            next_stop_data['eta_mins'] = max(1, int(dist_to_next * 3.0))
                    else:
                        next_stop_data = route_stops_data[-1]
                        next_stop_data['distance_km_to_next'] = 0.0
                        next_stop_data['eta_mins'] = 0

                    leg_a_to_c = route_stops_data[:current_idx + 1]
                    leg_c_to_f = route_stops_data[current_idx:]

            road_geometry = get_or_generate_road_geometry(bus.route) if bus.route else []

            return Response({
                "bus_id": bus.id,
                "bus_number": bus.bus_number,
                "bus_name": bus.bus_name,
                "bus_type": bus.get_bus_type_display(),
                "route_id": bus.route.id if bus.route else None,
                "route_name": bus.route.route_name if bus.route else "Unassigned",
                "tracking_status": bus.tracking_status,
                "last_updated": bus.last_updated,
                "latest_location": {
                    "latitude": loc.latitude if loc else None,
                    "longitude": loc.longitude if loc else None,
                    "speed": loc.speed if loc else 0.0,
                    "heading": loc.heading if loc else 0.0,
                    "timestamp": loc.timestamp.isoformat() if loc else None
                } if loc else None,
                "route_stops": route_stops_data,
                "current_stop": current_stop_data,
                "next_stop": next_stop_data,
                "leg_a_to_c": leg_a_to_c,
                "leg_c_to_f": leg_c_to_f,
                "road_geometry": road_geometry
            })
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=404)


class RouteGeometryAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        if pk:
            try:
                route = Route.objects.get(pk=pk)
                geometry = get_or_generate_road_geometry(route)
                stops = [
                    {
                        "id": rs.bus_stop.id,
                        "name": rs.bus_stop.stop_name,
                        "lat": rs.bus_stop.latitude,
                        "lng": rs.bus_stop.longitude,
                        "order": rs.stop_order
                    }
                    for rs in route.get_ordered_stops()
                ]
                return Response({
                    "route_id": route.id,
                    "route_name": route.route_name,
                    "stops": stops,
                    "road_geometry": geometry
                })
            except Route.DoesNotExist:
                return Response({"error": "Route not found."}, status=404)
        return Response({"message": "Send POST request with {'coordinates': [[lat, lon], ...]} to fetch OSRM road geometry."})

    def post(self, request, pk=None):
        coordinates = request.data.get('coordinates', [])
        if not coordinates or len(coordinates) < 2:
            return Response({
                "status": "error",
                "message": "At least 2 coordinate pairs [[lat, lon], ...] are required."
            }, status=400)

        # Convert [lat, lon] to float tuples
        formatted_coords = []
        for c in coordinates:
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                try:
                    lat = float(c[0])
                    lon = float(c[1])
                    formatted_coords.append((lat, lon))
                except (ValueError, TypeError):
                    continue

        if len(formatted_coords) < 2:
            return Response({
                "status": "error",
                "message": "Valid float [lat, lon] pairs are required."
            }, status=400)

        # Constraint 1: Convert [lat, lon] to {lon},{lat} format for OSRM URL
        coord_strs = [f"{lon:.6f},{lat:.6f}" for lat, lon in formatted_coords]

        chunk_size = 20
        all_geojson_coords = []

        import urllib.request, json

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
                            coords = data['routes'][0]['geometry']['coordinates']
                            if all_geojson_coords and coords:
                                all_geojson_coords.extend(coords[1:])
                            else:
                                all_geojson_coords.extend(coords)
                            continue
            except Exception:
                pass

            # Fallback for chunk
            sub_coords = formatted_coords[i:i + chunk_size]
            fallback_geojson = [[lon, lat] for lat, lon in sub_coords]
            if all_geojson_coords and fallback_geojson:
                all_geojson_coords.extend(fallback_geojson[1:])
            else:
                all_geojson_coords.extend(fallback_geojson)

        if not all_geojson_coords:
            all_geojson_coords = [[lon, lat] for lat, lon in formatted_coords]

        road_lat_lng = [[c[1], c[0]] for c in all_geojson_coords]

        return Response({
            "status": "success",
            "geometry": {
                "type": "LineString",
                "coordinates": all_geojson_coords
            },
            "road_points": road_lat_lng
        })


def resolve_bus_by_no_or_id(bus_param):
    if not bus_param:
        return None
    param_str = str(bus_param).strip()
    if param_str.isdigit():
        b_id = Bus.objects.filter(id=int(param_str)).first()
        if b_id:
            return b_id
    b_exact = Bus.objects.filter(bus_number__iexact=param_str).first()
    if b_exact:
        return b_exact
    return Bus.objects.filter(bus_number__icontains=param_str).first()


class DriverTripStartAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        bus_no = request.data.get('bus_no') or request.data.get('bus_number') or request.query_params.get('bus_no')
        route_id = request.data.get('route_id') or request.query_params.get('route_id')

        bus = resolve_bus_by_no_or_id(bus_no)
        if not bus:
            return Response({"status": "error", "error": f"Bus '{bus_no}' not found."}, status=404)

        if route_id:
            r_obj = Route.objects.filter(id=route_id).first()
            if r_obj:
                bus.route = r_obj

        bus.trip_status = 'IN_TRANSIT'
        bus.tracking_status = 'LIVE'
        bus.last_updated = timezone.now()
        bus.save()

        return Response({
            "status": "success",
            "message": "Trip started successfully.",
            "bus_no": bus.bus_number,
            "trip_status": bus.trip_status,
            "tracking_status": bus.tracking_status
        })


class DriverTripUpdateLocationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        bus_no = request.data.get('bus_no') or request.data.get('bus_number') or request.query_params.get('bus_no')
        lat = request.data.get('lat') or request.data.get('latitude')
        lon = request.data.get('lon') or request.data.get('lng') or request.data.get('longitude')
        speed = request.data.get('speed', 0.0)
        heading = request.data.get('heading', 0.0)

        if lat is None or lon is None:
            return Response({"status": "error", "error": "'lat' and 'lon' parameters are required."}, status=400)

        bus = resolve_bus_by_no_or_id(bus_no)
        if not bus:
            return Response({"status": "error", "error": f"Bus '{bus_no}' not found."}, status=404)

        bus.tracking_status = 'LIVE'
        bus.last_updated = timezone.now()
        bus.save(update_fields=['tracking_status', 'last_updated'])

        loc = BusLocation.objects.create(
            bus=bus,
            latitude=float(lat),
            longitude=float(lon),
            speed=float(speed or 0.0),
            heading=float(heading or 0.0),
            timestamp=timezone.now()
        )

        return Response({
            "status": "success",
            "message": "Location updated successfully.",
            "bus_no": bus.bus_number,
            "current_lat": loc.latitude,
            "current_lon": loc.longitude,
            "speed_kmh": loc.speed,
            "heading": loc.heading
        })


class DriverTripEndAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        bus_no = request.data.get('bus_no') or request.data.get('bus_number') or request.query_params.get('bus_no')

        bus = resolve_bus_by_no_or_id(bus_no)
        if not bus:
            return Response({"status": "error", "error": f"Bus '{bus_no}' not found."}, status=404)

        bus.trip_status = 'COMPLETED'
        bus.tracking_status = 'OFFLINE'
        bus.last_updated = timezone.now()
        bus.save()

        return Response({
            "status": "success",
            "message": "Trip completed.",
            "bus_no": bus.bus_number,
            "trip_status": bus.trip_status,
            "tracking_status": bus.tracking_status
        })


class PassengerBusLiveStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, bus_no=None):
        if not bus_no:
            bus_no = request.query_params.get('bus_no') or request.query_params.get('bus_number')

        bus = resolve_bus_by_no_or_id(bus_no)
        if not bus:
            return Response({
                "bus_no": str(bus_no or ""),
                "is_live": False,
                "status": "OFFLINE",
                "current_lat": None,
                "current_lon": None,
                "speed_kmh": 0.0,
                "heading": 0.0,
                "last_updated_seconds_ago": None
            })

        loc = bus.get_current_location()
        seconds_ago = int((timezone.now() - loc.timestamp).total_seconds()) if loc and loc.timestamp else None

        is_live = (bus.trip_status == 'IN_TRANSIT') and (loc is not None) and (seconds_ago is not None and seconds_ago <= 300)
        status_str = "IN_TRANSIT" if is_live else "OFFLINE"

        return Response({
            "bus_no": bus.bus_number,
            "is_live": is_live,
            "status": status_str,
            "current_lat": float(loc.latitude) if (loc and is_live) else (float(loc.latitude) if loc else None),
            "current_lon": float(loc.longitude) if (loc and is_live) else (float(loc.longitude) if loc else None),
            "speed_kmh": float(loc.speed) if loc else 0.0,
            "heading": float(loc.heading) if loc else 0.0,
            "last_updated_seconds_ago": seconds_ago
        })

