import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class BusTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.bus_id = self.scope['url_route']['kwargs'].get('bus_id')
        self.bus_group_name = f'bus_{self.bus_id}' if self.bus_id else 'bus_all'

        # Join bus specific channel group
        await self.channel_layer.group_add(
            self.bus_group_name,
            self.channel_name
        )

        # Join global bus overview channel group as well
        await self.channel_layer.group_add(
            'bus_all',
            self.channel_name
        )

        await self.accept()

        # Send initial status & current position if bus_id exists, or for all active buses
        if self.bus_id:
            bus_data = await self.get_latest_bus_data(self.bus_id)
            if bus_data:
                await self.send(text_data=json.dumps({
                    'type': 'initial_state',
                    'bus_data': bus_data
                }))
        else:
            buses_data = await self.get_all_latest_buses_data()
            if buses_data:
                await self.send(text_data=json.dumps({
                    'type': 'initial_state',
                    'buses_data': buses_data
                }))

    async def disconnect(self, close_code):
        # Leave channel groups
        await self.channel_layer.group_discard(
            self.bus_group_name,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            'bus_all',
            self.channel_name
        )

    # Receive message from WebSocket (sent by driver/GPS device)
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action') or data.get('type')

            if action in ['location_update', 'update_location']:
                bus_id = data.get('bus_id') or self.bus_id
                latitude = float(data.get('latitude'))
                longitude = float(data.get('longitude'))
                speed = float(data.get('speed', 0.0))
                heading = float(data.get('heading', 0.0))
                status = data.get('status', 'LIVE')

                if bus_id and latitude and longitude:
                    # Save location to DB asynchronously
                    bus_update = await self.save_bus_location(bus_id, latitude, longitude, speed, heading, status)

                    if bus_update:
                        payload = {
                            'type': 'bus_location_broadcast',
                            'bus_id': int(bus_id),
                            'bus_number': bus_update['bus_number'],
                            'bus_name': bus_update['bus_name'],
                            'bus_type': bus_update['bus_type'],
                            'latitude': latitude,
                            'longitude': longitude,
                            'speed': speed,
                            'heading': heading,
                            'status': status,
                            'timestamp': bus_update['timestamp']
                        }

                        # Broadcast to specific bus channel group
                        await self.channel_layer.group_send(
                            f'bus_{bus_id}',
                            payload
                        )

                        # Broadcast to global all-bus channel group
                        await self.channel_layer.group_send(
                            'bus_all',
                            payload
                        )
            elif action in ['trip_end', 'stop_trip', 'trip_stop']:
                bus_id = data.get('bus_id') or self.bus_id
                if bus_id:
                    bus_update = await self.end_bus_trip(bus_id)
                    payload = {
                        'type': 'bus_location_broadcast',
                        'bus_id': int(bus_id),
                        'bus_number': bus_update['bus_number'] if bus_update else '',
                        'bus_name': bus_update['bus_name'] if bus_update else '',
                        'bus_type': '',
                        'latitude': None,
                        'longitude': None,
                        'speed': 0.0,
                        'heading': 0.0,
                        'status': 'OFFLINE',
                        'timestamp': timezone.now().isoformat()
                    }
                    await self.channel_layer.group_send(f'bus_{bus_id}', payload)
                    await self.channel_layer.group_send('bus_all', payload)

            elif action == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    # Handler for channel layer group_send
    async def bus_location_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'bus_id': event['bus_id'],
            'bus_number': event['bus_number'],
            'bus_name': event['bus_name'],
            'bus_type': event['bus_type'],
            'latitude': event.get('latitude'),
            'longitude': event.get('longitude'),
            'speed': event.get('speed', 0.0),
            'heading': event.get('heading', 0.0),
            'status': event.get('status', 'LIVE'),
            'timestamp': event.get('timestamp')
        }))

    @database_sync_to_async
    def save_bus_location(self, bus_id, lat, lng, speed, heading, status):
        from tracking.models import Bus, BusLocation
        try:
            bus = Bus.objects.get(id=bus_id)
            bus.tracking_status = status
            if status == 'LIVE':
                bus.trip_status = 'IN_TRANSIT'
            elif status == 'OFFLINE':
                bus.trip_status = 'COMPLETED'
            bus.last_updated = timezone.now()
            bus.save(update_fields=['tracking_status', 'trip_status', 'last_updated'])

            loc = BusLocation.objects.create(
                bus=bus,
                latitude=lat,
                longitude=lng,
                speed=speed,
                heading=heading,
                timestamp=timezone.now()
            )
            return {
                'bus_number': bus.bus_number,
                'bus_name': bus.bus_name,
                'bus_type': bus.get_bus_type_display(),
                'timestamp': loc.timestamp.isoformat()
            }
        except Bus.DoesNotExist:
            return None

    @database_sync_to_async
    def end_bus_trip(self, bus_id):
        from tracking.models import Bus
        try:
            bus = Bus.objects.get(id=bus_id)
            bus.tracking_status = 'OFFLINE'
            bus.trip_status = 'COMPLETED'
            bus.last_updated = timezone.now()
            bus.save(update_fields=['tracking_status', 'trip_status', 'last_updated'])
            return {
                'bus_number': bus.bus_number,
                'bus_name': bus.bus_name
            }
        except Bus.DoesNotExist:
            return None

    @database_sync_to_async
    def get_latest_bus_data(self, bus_id):
        from tracking.models import Bus
        try:
            bus = Bus.objects.get(id=bus_id)
            loc = bus.get_current_location()
            return {
                'bus_id': bus.id,
                'bus_number': bus.bus_number,
                'bus_name': bus.bus_name,
                'bus_type': bus.get_bus_type_display(),
                'route_name': bus.route.route_name if bus.route else "Unassigned",
                'status': bus.tracking_status,
                'latitude': loc.latitude if loc else None,
                'longitude': loc.longitude if loc else None,
                'speed': loc.speed if loc else 0.0,
                'heading': loc.heading if loc else 0.0,
                'timestamp': loc.timestamp.isoformat() if loc else None
            }
        except Bus.DoesNotExist:
            return None

    @database_sync_to_async
    def get_all_latest_buses_data(self):
        from tracking.models import Bus
        # STRICT REAL-TIME: Only return buses that are actively IN_TRANSIT and LIVE
        buses = Bus.objects.filter(is_active=True, tracking_status='LIVE', trip_status='IN_TRANSIT').select_related('route')
        buses_list = []
        for bus in buses:
            loc = bus.get_current_location()
            if loc:
                buses_list.append({
                    'bus_id': bus.id,
                    'bus_number': bus.bus_number,
                    'bus_name': bus.bus_name,
                    'bus_type': bus.get_bus_type_display(),
                    'route_name': bus.route.route_name if bus.route else "Unassigned",
                    'status': bus.tracking_status,
                    'latitude': loc.latitude,
                    'longitude': loc.longitude,
                    'speed': loc.speed,
                    'heading': loc.heading,
                    'timestamp': loc.timestamp.isoformat()
                })
        return buses_list
