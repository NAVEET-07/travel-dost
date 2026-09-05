from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.contrib import messages

from tracking.models import User, BusStop, Route, RouteStop, Bus, GPSDevice, BusLocation, Fare, BusTrackingSession, SearchHistory
from tracking.decorators import admin_required, driver_required, user_required


def home_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.is_admin():
        return redirect('admin-dashboard')
    elif request.user.is_driver():
        return redirect('driver-portal')
    return redirect('user-dashboard')


@login_required(login_url='login')
def route_finder_view(request):
    stops = BusStop.objects.filter(is_active=True).order_by('stop_name')
    source_id = request.GET.get('source')
    dest_id = request.GET.get('destination')

    context = {
        'stops': stops,
        'selected_source': int(source_id) if source_id and source_id.isdigit() else None,
        'selected_dest': int(dest_id) if dest_id and dest_id.isdigit() else None,
    }
    return render(request, 'route_finder.html', context)


@login_required(login_url='login')
def live_tracking_view(request, bus_id=None):
    buses = Bus.objects.filter(is_active=True).select_related('route')
    selected_bus = None
    if bus_id:
        selected_bus = get_object_or_404(Bus, id=bus_id)
    elif request.GET.get('bus_id'):
        b_id = request.GET.get('bus_id')
        if b_id.isdigit():
            selected_bus = Bus.objects.filter(id=int(b_id)).first()

    all_stops = BusStop.objects.filter(is_active=True)

    context = {
        'buses': buses,
        'selected_bus': selected_bus,
        'all_stops': all_stops,
    }
    return render(request, 'live_tracking.html', context)


@login_required(login_url='login')
def nearby_stops_view(request):
    return render(request, 'nearby_stops.html')


@login_required(login_url='login')
def bus_list_view(request):
    query = request.GET.get('q', '')
    bus_type = request.GET.get('type', '')

    buses = Bus.objects.filter(is_active=True).select_related('route')
    if query:
        buses = buses.filter(Q(bus_number__icontains=query) | Q(bus_name__icontains=query) | Q(route__route_name__icontains=query))
    if bus_type:
        buses = buses.filter(bus_type=bus_type)

    context = {
        'buses': buses,
        'query': query,
        'selected_type': bus_type,
        'type_choices': Bus.BUS_TYPE_CHOICES
    }
    return render(request, 'buses.html', context)


@login_required(login_url='login')
def bus_detail_view(request, pk):
    bus = get_object_or_404(Bus.objects.select_related('route'), pk=pk)
    current_loc = bus.get_current_location()
    location_history = bus.locations.order_by('-timestamp')[:10]

    context = {
        'bus': bus,
        'current_loc': current_loc,
        'location_history': location_history,
    }
    return render(request, 'bus_detail.html', context)


@login_required(login_url='login')
def route_list_view(request):
    routes = Route.objects.filter(is_active=True).annotate(stops_cnt=Count('route_stops'))
    return render(request, 'routes.html', {'routes': routes})


@login_required(login_url='login')
def route_detail_view(request, pk):
    route = get_object_or_404(Route, pk=pk)
    route_stops = route.route_stops.select_related('bus_stop').order_by('stop_order')
    assigned_buses = route.buses.filter(is_active=True)

    context = {
        'route': route,
        'route_stops': route_stops,
        'assigned_buses': assigned_buses,
    }
    return render(request, 'route_detail.html', context)


@login_required(login_url='login')
def stop_list_view(request):
    stops = BusStop.objects.filter(is_active=True).annotate(routes_cnt=Count('stop_routes'))
    return render(request, 'stops.html', {'stops': stops})


@login_required(login_url='login')
def stop_detail_view(request, pk):
    stop = get_object_or_404(BusStop, pk=pk)
    passing_routes = RouteStop.objects.filter(bus_stop=stop).select_related('route').order_by('route__route_name')

    context = {
        'stop': stop,
        'passing_routes': passing_routes,
    }
    return render(request, 'stop_detail.html', context)


# -------------------------------------------------------------------
# ROLE BASED DASHBOARDS & LOGINS
# -------------------------------------------------------------------
@driver_required
def driver_portal_view(request):
    # Fetch driver's assigned buses or fall back to any active bus
    driver_buses = Bus.objects.filter(Q(driver=request.user) | Q(is_active=True), is_active=True).select_related('route').order_by('bus_number')
    
    bus_id = request.GET.get('bus_id')
    assigned_bus = None
    if bus_id and bus_id.isdigit():
        assigned_bus = driver_buses.filter(id=int(bus_id)).first()
    if not assigned_bus:
        assigned_bus = driver_buses.filter(driver=request.user).first() or driver_buses.first()

    context = {
        'assigned_bus': assigned_bus,
        'driver_buses': driver_buses,
    }
    return render(request, 'driver_portal.html', context)



@admin_required
def admin_dashboard_view(request):
    total_buses = Bus.objects.count()
    active_buses = Bus.objects.filter(is_active=True).count()
    live_buses = Bus.objects.filter(tracking_status='LIVE').count()
    total_routes = Route.objects.count()
    total_stops = BusStop.objects.count()
    total_users = User.objects.count()
    total_devices = GPSDevice.objects.count()
    active_sessions = BusTrackingSession.objects.filter(status='ACTIVE').count()

    recent_searches = SearchHistory.objects.all()[:10]
    buses = Bus.objects.select_related('route', 'driver').all()
    routes = Route.objects.filter(is_active=True).prefetch_related('route_stops__bus_stop').all()
    stops = BusStop.objects.filter(is_active=True).order_by('stop_name')
    drivers = User.objects.filter(role='DRIVER')

    context = {
        'total_buses': total_buses,
        'active_buses': active_buses,
        'live_buses': live_buses,
        'total_routes': total_routes,
        'total_stops': total_stops,
        'total_users': total_users,
        'total_devices': total_devices,
        'active_sessions': active_sessions,
        'recent_searches': recent_searches,
        'buses': buses,
        'routes': routes,
        'stops': stops,
        'drivers': drivers,
    }
    return render(request, 'admin_dashboard.html', context)


@admin_required
def admin_add_bus_view(request):
    if request.method == 'POST':
        bus_number = request.POST.get('bus_number')
        bus_name = request.POST.get('bus_name')
        bus_type = request.POST.get('bus_type', 'ORDINARY')
        route_id = request.POST.get('route_id')
        driver_id = request.POST.get('driver_id')

        route = Route.objects.filter(id=route_id).first() if route_id else None
        driver = User.objects.filter(id=driver_id, role='DRIVER').first() if driver_id else None

        if bus_number:
            Bus.objects.create(
                bus_number=bus_number,
                bus_name=bus_name or f"Bus {bus_number}",
                bus_type=bus_type,
                route=route,
                driver=driver
            )
            messages.success(request, f"Bus {bus_number} added successfully!")
        else:
            messages.error(request, "Bus number is required.")

    return redirect('admin-dashboard')


@admin_required
def admin_edit_bus_view(request, pk):
    bus = get_object_or_404(Bus, pk=pk)
    if request.method == 'POST':
        bus.bus_number = request.POST.get('bus_number', bus.bus_number)
        bus.bus_name = request.POST.get('bus_name', bus.bus_name)
        bus.bus_type = request.POST.get('bus_type', bus.bus_type)

        route_id = request.POST.get('route_id')
        driver_id = request.POST.get('driver_id')

        bus.route = Route.objects.filter(id=route_id).first() if route_id else None
        bus.driver = User.objects.filter(id=driver_id, role='DRIVER').first() if driver_id else None
        bus.save()

        messages.success(request, f"Bus {bus.bus_number} updated successfully!")

    return redirect('admin-dashboard')


@admin_required
def admin_delete_bus_view(request, pk):
    bus = get_object_or_404(Bus, pk=pk)
    if request.method in ['POST', 'GET']:
        bus_num = bus.bus_number
        bus.delete()
        messages.success(request, f"Bus {bus_num} deleted successfully!")
    return redirect('admin-dashboard')


@user_required
def user_dashboard_view(request):
    stops = BusStop.objects.filter(is_active=True).order_by('stop_name')
    routes = Route.objects.filter(is_active=True)
    buses = Bus.objects.filter(is_active=True).select_related('route')
    fares = Fare.objects.select_related('route', 'source_stop', 'destination_stop').all()

    context = {
        'stops': stops,
        'routes': routes,
        'buses': buses,
        'fares': fares,
    }
    return render(request, 'user_dashboard.html', context)


def admin_login_view(request):
    return redirect('login')


def driver_login_view(request):
    return redirect('login')


def login_ui_view(request):
    if request.user.is_authenticated:
        if request.user.is_admin():
            return redirect('admin-dashboard')
        elif request.user.is_driver():
            return redirect('driver-portal')
        return redirect('user-dashboard')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('login')


def register_ui_view(request):
    if request.user.is_authenticated:
        return redirect('user-dashboard')
    return render(request, 'register.html')


def about_view(request):
    return render(request, 'about.html')

