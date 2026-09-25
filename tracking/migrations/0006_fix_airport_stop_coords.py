from django.db import migrations


def fix_airport_coords(apps, schema_editor):
    BusStop = apps.get_model('tracking', 'BusStop')
    Route = apps.get_model('tracking', 'Route')

    # Update Airport stop coordinates to Gokul Road bus shelter location
    # (prevents routing engine from entering internal airport terminal loop)
    stops = BusStop.objects.filter(stop_name__iexact='Airport')
    for s in stops:
        s.latitude = 15.355375
        s.longitude = 75.085810
        s.save(update_fields=['latitude', 'longitude'])

    # Invalidate cached shape_geometry for routes passing through Airport stop
    for s in stops:
        affected_routes = Route.objects.filter(route_stops__bus_stop=s).distinct()
        for r in affected_routes:
            r.shape_geometry = []
            r.save(update_fields=['shape_geometry'])


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0005_alter_bus_trip_status'),
    ]

    operations = [
        migrations.RunPython(fix_airport_coords, reverse_fix),
    ]
