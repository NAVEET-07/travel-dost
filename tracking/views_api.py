from rest_framework import status, viewsets, generics
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
from tracking.services.route_finder import find_best_routes


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
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminRoleOrStaff()]


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
class RouteSearchAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        source_id = request.query_params.get('source')
        dest_id = request.query_params.get('destination')

        if not source_id or not dest_id:
            return Response({"error": "Both 'source' and 'destination' query params are required."}, status=400)

        # Log search history if user is authenticated
        source_stop = BusStop.objects.filter(id=source_id).first()
        dest_stop = BusStop.objects.filter(id=dest_id).first()
        if source_stop and dest_stop:
            SearchHistory.objects.create(
                user=request.user if request.user.is_authenticated else None,
                source_stop_name=source_stop.stop_name,
                destination_stop_name=dest_stop.stop_name
            )

        results = find_best_routes(source_id, dest_id)
        return Response(results)


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
            bus = Bus.objects.get(pk=pk)
            loc = bus.get_current_location()
            return Response({
                "bus_id": bus.id,
                "bus_number": bus.bus_number,
                "bus_name": bus.bus_name,
                "bus_type": bus.get_bus_type_display(),
                "route_name": bus.route.route_name if bus.route else "Unassigned",
                "tracking_status": bus.tracking_status,
                "last_updated": bus.last_updated,
                "latest_location": {
                    "latitude": loc.latitude if loc else None,
                    "longitude": loc.longitude if loc else None,
                    "speed": loc.speed if loc else 0.0,
                    "heading": loc.heading if loc else 0.0,
                    "timestamp": loc.timestamp if loc else None
                } if loc else None
            })
        except Bus.DoesNotExist:
            return Response({"error": "Bus not found."}, status=404)
