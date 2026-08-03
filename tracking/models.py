from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = (
        ('USER', 'User'),
        ('PASSENGER', 'Passenger'),
        ('DRIVER', 'Driver'),
        ('ADMIN', 'Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    def is_admin(self):
        return self.role == 'ADMIN' or self.is_staff or self.is_superuser

    def is_driver(self):
        return self.role == 'DRIVER'

    def is_user(self):
        return self.role in ['USER', 'PASSENGER']

    def is_passenger(self):
        return self.is_user()


class BusStop(models.Model):
    stop_name = models.CharField(max_length=150, unique=True)
    area = models.CharField(max_length=150, help_text="Area / Suburb e.g. Vidya Nagar, Hosur")
    latitude = models.FloatField(help_text="GPS Latitude e.g. 15.3647")
    longitude = models.FloatField(help_text="GPS Longitude e.g. 75.1240")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['stop_name']
        verbose_name = "Bus Stop"
        verbose_name_plural = "Bus Stops"

    def __str__(self):
        return f"{self.stop_name} ({self.area})"


class Route(models.Model):
    route_name = models.CharField(max_length=150, help_text="e.g. Route 101: CBT Hubballi to Dharwad CBT")
    start_point = models.CharField(max_length=150)
    end_point = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['route_name']

    def __str__(self):
        return self.route_name

    def get_ordered_stops(self):
        return self.route_stops.select_related('bus_stop').order_by('stop_order')


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='route_stops')
    bus_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='stop_routes')
    stop_order = models.PositiveIntegerField(help_text="Order sequence of stop on route (1, 2, 3...)")
    distance_from_start_km = models.FloatField(default=0.0, help_text="Cumulative distance from start stop in KM")

    class Meta:
        ordering = ['route', 'stop_order']
        unique_together = ('route', 'stop_order')

    def __str__(self):
        return f"{self.route.route_name} - Stop #{self.stop_order}: {self.bus_stop.stop_name}"


class Bus(models.Model):
    BUS_TYPE_CHOICES = (
        ('ORDINARY', 'NWKRTC Ordinary'),
        ('EXPRESS', 'NWKRTC Express'),
        ('BRTS', 'Chigari BRTS Express'),
    )
    STATUS_CHOICES = (
        ('LIVE', 'Live Tracking Active'),
        ('OFFLINE', 'Offline / Not Tracking'),
        ('LAST_SEEN', 'Last Seen (Inactive)'),
    )
    bus_number = models.CharField(max_length=50, unique=True, help_text="e.g. KA-25-F-101")
    bus_name = models.CharField(max_length=100, default="NWKRTC Bus")
    bus_type = models.CharField(max_length=20, choices=BUS_TYPE_CHOICES, default='ORDINARY')
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name='buses')
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'role': 'DRIVER'}, related_name='assigned_buses')
    is_active = models.BooleanField(default=True)
    tracking_enabled = models.BooleanField(default=True)
    tracking_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE')
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Buses"

    def __str__(self):
        return f"Bus {self.bus_number} ({self.get_bus_type_display()})"

    def get_current_location(self):
        return self.locations.order_by('-timestamp').first()


class GPSDevice(models.Model):
    device_id = models.CharField(max_length=100, unique=True, help_text="Unique device identifier / Serial / Phone ID")
    device_name = models.CharField(max_length=100, help_text="e.g. Driver Mobile - Samsung Galaxy")
    assigned_bus = models.OneToOneField(Bus, on_delete=models.SET_NULL, null=True, blank=True, related_name='gps_device')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='gps_devices')
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        bus_str = self.assigned_bus.bus_number if self.assigned_bus else "Unassigned"
        return f"{self.device_name} ({self.device_id}) -> Bus {bus_str}"


class BusLocation(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='locations')
    latitude = models.FloatField()
    longitude = models.FloatField()
    speed = models.FloatField(default=0.0, help_text="Speed in km/h")
    heading = models.FloatField(default=0.0, help_text="Heading angle in degrees (0-360)")
    timestamp = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['bus', '-timestamp']),
        ]

    def __str__(self):
        return f"Bus {self.bus.bus_number} @ ({self.latitude:.5f}, {self.longitude:.5f}) at {self.timestamp.strftime('%H:%M:%S')}"


class BusTrackingSession(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='tracking_sessions')
    gps_device = models.ForeignKey(GPSDevice, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='ACTIVE')

    def __str__(self):
        return f"Session for Bus {self.bus.bus_number} (Started: {self.started_at.strftime('%Y-%m-%d %H:%M')})"


class Fare(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='fares')
    source_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='source_fares')
    destination_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='destination_fares')
    fare_amount = models.DecimalField(max_digits=8, decimal_places=2)
    fare_type = models.CharField(max_length=50, default="Standard Adult", help_text="e.g. Standard, Student, Express")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('route', 'source_stop', 'destination_stop', 'fare_type')

    def __str__(self):
        return f"{self.route.route_name}: {self.source_stop.stop_name} → {self.destination_stop.stop_name} = ₹{self.fare_amount}"


class SearchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='search_history')
    source_stop_name = models.CharField(max_length=150)
    destination_stop_name = models.CharField(max_length=150)
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-searched_at']

    def __str__(self):
        return f"Search: {self.source_stop_name} → {self.destination_stop_name} at {self.searched_at.strftime('%Y-%m-%d %H:%M')}"
