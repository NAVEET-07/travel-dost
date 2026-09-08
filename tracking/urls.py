from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tracking import views_ui, views_api

router = DefaultRouter()
router.register(r'buses', views_api.BusViewSet, basename='api-bus')
router.register(r'routes', views_api.RouteViewSet, basename='api-route')
router.register(r'stops', views_api.BusStopViewSet, basename='api-stop')
router.register(r'fares', views_api.FareViewSet, basename='api-fare')
router.register(r'gps-devices', views_api.GPSDeviceViewSet, basename='api-gps-device')

urlpatterns = [
    # Role-Based Specific URLs & Portals
    path('admin/login/', views_ui.admin_login_view, name='admin-login'),
    path('admin/dashboard/', views_ui.admin_dashboard_view, name='admin-dashboard'),
    path('admin-dashboard/', views_ui.admin_dashboard_view, name='admin-dashboard-alias'),
    path('admin/bus/add/', views_ui.admin_add_bus_view, name='admin-add-bus'),
    path('admin/bus/edit/<int:pk>/', views_ui.admin_edit_bus_view, name='admin-edit-bus'),
    path('admin/bus/delete/<int:pk>/', views_ui.admin_delete_bus_view, name='admin-delete-bus'),

    path('driver/login/', views_ui.driver_login_view, name='driver-login'),
    path('driver/dashboard/', views_ui.driver_portal_view, name='driver-dashboard'),
    path('driver/', views_ui.driver_portal_view, name='driver-portal'),
    path('gps-device/', views_ui.driver_portal_view, name='gps-device-portal'),

    path('login/', views_ui.login_ui_view, name='login'),
    path('logout/', views_ui.logout_view, name='logout'),
    path('register/', views_ui.register_ui_view, name='register'),
    path('dashboard/', views_ui.user_dashboard_view, name='user-dashboard'),
    path('tracking/', views_ui.live_tracking_view, name='tracking'),
    path('live-tracking/', views_ui.live_tracking_view, name='live-tracking'),
    path('live-tracking/<int:bus_id>/', views_ui.live_tracking_view, name='live-tracking-bus'),

    # General Web Application Pages
    path('', views_ui.home_view, name='home'),
    path('find-route/', views_ui.route_finder_view, name='route-finder'),
    path('nearby-stops/', views_ui.nearby_stops_view, name='nearby-stops'),
    path('buses/', views_ui.bus_list_view, name='buses'),
    path('buses/<int:pk>/', views_ui.bus_detail_view, name='bus-detail'),
    path('routes/', views_ui.route_list_view, name='routes'),
    path('routes/<int:pk>/', views_ui.route_detail_view, name='route-detail'),
    path('transit-map/', views_ui.transit_map_view, name='transit-map'),
    path('route-map/', views_ui.transit_map_view, name='route-map'),
    path('stops/', views_ui.stop_list_view, name='stops'),
    path('stops/<int:pk>/', views_ui.stop_detail_view, name='stop-detail'),
    path('about/', views_ui.about_view, name='about'),

    # REST APIs
    path('api/auth/register/', views_api.RegisterAPIView.as_view(), name='api-register'),
    path('api/auth/login/', views_api.LoginAPIView.as_view(), name='api-login'),
    path('api/auth/logout/', views_api.LogoutAPIView.as_view(), name='api-logout'),
    path('api/stops/autocomplete/', views_api.StopsAutocompleteAPIView.as_view(), name='api-stops-autocomplete'),
    path('api/stops/autocomplete', views_api.StopsAutocompleteAPIView.as_view()),
    path('api/stops/names/', views_api.StopsAutocompleteAPIView.as_view(), name='api-stops-names'),
    path('api/stops/names', views_api.StopsAutocompleteAPIView.as_view()),
    path('api/routes/search/', views_api.RouteSearchAPIView.as_view(), name='api-routes-search'),
    path('api/routes/search', views_api.RouteSearchAPIView.as_view()),
    path('api/search-route/', views_api.RouteSearchAPIView.as_view(), name='api-search-route'),
    path('api/search-route', views_api.RouteSearchAPIView.as_view()),
    path('api/nearby-stops/', views_api.NearbyStopsAPIView.as_view(), name='api-nearby-stops'),
    path('api/buses/<int:pk>/location/', views_api.BusLocationAPIView.as_view(), name='api-bus-location'),
    path('api/buses/<int:pk>/tracking-status/', views_api.BusTrackingStatusAPIView.as_view(), name='api-bus-tracking-status'),
    path('api/routes/<int:pk>/geometry/', views_api.RouteGeometryAPIView.as_view(), name='api-route-geometry'),
    path('api/routes/road-geometry/', views_api.RouteGeometryAPIView.as_view(), name='api-road-geometry'),
    path('api/routes/road-geometry', views_api.RouteGeometryAPIView.as_view()),
    path('api/routes/<int:pk>/add-stop/', views_api.AddRouteStopAPIView.as_view(), name='api-add-route-stop'),

    # Driver Trip Lifecycle Endpoints
    path('api/driver/trip/start/', views_api.DriverTripStartAPIView.as_view(), name='api-driver-trip-start'),
    path('api/driver/trip/start', views_api.DriverTripStartAPIView.as_view()),
    path('api/driver/trip/update-location/', views_api.DriverTripUpdateLocationAPIView.as_view(), name='api-driver-trip-update-location'),
    path('api/driver/trip/update-location', views_api.DriverTripUpdateLocationAPIView.as_view()),
    path('api/driver/trip/end/', views_api.DriverTripEndAPIView.as_view(), name='api-driver-trip-end'),
    path('api/driver/trip/end', views_api.DriverTripEndAPIView.as_view()),

    # Passenger Live Bus Status Endpoint
    path('api/bus/<str:bus_no>/live-status/', views_api.PassengerBusLiveStatusAPIView.as_view(), name='api-bus-live-status'),
    path('api/bus/<str:bus_no>/live-status', views_api.PassengerBusLiveStatusAPIView.as_view()),

    path('api/route-stops/<int:pk>/delete/', views_api.DeleteRouteStopAPIView.as_view(), name='api-delete-route-stop'),
    path('api/', include(router.urls)),
]
