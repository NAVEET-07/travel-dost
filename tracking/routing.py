from django.urls import re_path
from tracking.consumers import BusTrackingConsumer

websocket_urlpatterns = [
    re_path(r'^ws/bus-tracking/(?P<bus_id>\d+)/$', BusTrackingConsumer.as_asgi()),
    re_path(r'^ws/bus-tracking/$', BusTrackingConsumer.as_asgi()),
]
