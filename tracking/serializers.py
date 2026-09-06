from rest_framework import serializers
from tracking.models import User, BusStop, Route, RouteStop, Bus, GPSDevice, BusLocation, Fare, BusTrackingSession, SearchHistory


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=4)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class BusStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusStop
        fields = ['id', 'stop_name', 'area', 'latitude', 'longitude', 'description', 'is_active']


class RouteStopSerializer(serializers.ModelSerializer):
    bus_stop = BusStopSerializer(read_only=True)
    bus_stop_id = serializers.PrimaryKeyRelatedField(
        queryset=BusStop.objects.all(), source='bus_stop', write_only=True
    )

    class Meta:
        model = RouteStop
        fields = ['id', 'stop_order', 'distance_from_start_km', 'bus_stop', 'bus_stop_id']


class RouteSerializer(serializers.ModelSerializer):
    route_stops = RouteStopSerializer(many=True, read_only=True)
    total_stops = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = ['id', 'route_name', 'start_point', 'end_point', 'description', 'is_active', 'total_stops', 'route_stops']

    def get_total_stops(self, obj):
        return obj.route_stops.count()


class BusLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusLocation
        fields = ['id', 'bus', 'latitude', 'longitude', 'speed', 'heading', 'timestamp', 'is_active']


class BusSerializer(serializers.ModelSerializer):
    route = RouteSerializer(read_only=True)
    route_id = serializers.PrimaryKeyRelatedField(
        queryset=Route.objects.all(), source='route', write_only=True, required=False, allow_null=True
    )
    driver_username = serializers.CharField(source='driver.username', read_only=True, allow_null=True)
    driver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='DRIVER'), source='driver', write_only=True, required=False, allow_null=True
    )
    current_location = serializers.SerializerMethodField()
    bus_type_display = serializers.CharField(source='get_bus_type_display', read_only=True)

    class Meta:
        model = Bus
        fields = [
            'id', 'bus_number', 'bus_name', 'bus_type', 'bus_type_display',
            'route', 'route_id', 'driver', 'driver_id', 'driver_username',
            'is_active', 'tracking_enabled', 'tracking_status', 'trip_status',
            'last_updated', 'current_location'
        ]

    def get_current_location(self, obj):
        loc = obj.get_current_location()
        if loc:
            return BusLocationSerializer(loc).data
        return None


class GPSDeviceSerializer(serializers.ModelSerializer):
    assigned_bus_number = serializers.CharField(source='assigned_bus.bus_number', read_only=True)

    class Meta:
        model = GPSDevice
        fields = ['id', 'device_id', 'device_name', 'assigned_bus', 'assigned_bus_number', 'user', 'is_active', 'last_seen']


class FareSerializer(serializers.ModelSerializer):
    route_name = serializers.CharField(source='route.route_name', read_only=True)
    source_stop_name = serializers.CharField(source='source_stop.stop_name', read_only=True)
    destination_stop_name = serializers.CharField(source='destination_stop.stop_name', read_only=True)

    class Meta:
        model = Fare
        fields = [
            'id', 'route', 'route_name', 'source_stop', 'source_stop_name',
            'destination_stop', 'destination_stop_name', 'fare_amount', 'fare_type', 'last_updated'
        ]


class BusTrackingSessionSerializer(serializers.ModelSerializer):
    bus_number = serializers.CharField(source='bus.bus_number', read_only=True)

    class Meta:
        model = BusTrackingSession
        fields = ['id', 'bus', 'bus_number', 'gps_device', 'started_at', 'ended_at', 'status']


class SearchHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchHistory
        fields = ['id', 'user', 'source_stop_name', 'destination_stop_name', 'searched_at']
