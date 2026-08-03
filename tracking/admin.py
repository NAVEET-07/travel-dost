from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from tracking.models import User, BusStop, Route, RouteStop, Bus, GPSDevice, BusLocation, BusTrackingSession, Fare, SearchHistory


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Role & Attributes', {'fields': ('role', 'phone_number')}),
    )


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_name', 'start_point', 'end_point', 'is_active', 'created_at')
    search_fields = ('route_name', 'start_point', 'end_point')
    inlines = [RouteStopInline]


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ('stop_name', 'area', 'latitude', 'longitude', 'is_active')
    search_fields = ('stop_name', 'area')
    list_filter = ('area', 'is_active')


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('bus_number', 'bus_name', 'bus_type', 'route', 'tracking_status', 'is_active', 'last_updated')
    list_filter = ('bus_type', 'tracking_status', 'is_active')
    search_fields = ('bus_number', 'bus_name')


@admin.register(GPSDevice)
class GPSDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'device_name', 'assigned_bus', 'user', 'is_active', 'last_seen')
    search_fields = ('device_id', 'device_name')


@admin.register(BusLocation)
class BusLocationAdmin(admin.ModelAdmin):
    list_display = ('bus', 'latitude', 'longitude', 'speed', 'heading', 'timestamp')
    list_filter = ('bus', 'timestamp')


@admin.register(Fare)
class FareAdmin(admin.ModelAdmin):
    list_display = ('route', 'source_stop', 'destination_stop', 'fare_amount', 'fare_type')
    list_filter = ('fare_type', 'route')


admin.site.register(User, CustomUserAdmin)
admin.site.register(BusTrackingSession)
admin.site.register(SearchHistory)
