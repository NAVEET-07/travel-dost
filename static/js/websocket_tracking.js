/* Travel Dost WebSocket Tracking Handler */

let trackingSocket = null;

function startBusTrackingSocket(busId) {
    if (trackingSocket) {
        trackingSocket.close();
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = busId && busId !== 'all' 
        ? `${wsProtocol}${window.location.host}/ws/bus-tracking/${busId}/`
        : `${wsProtocol}${window.location.host}/ws/bus-tracking/`;

    trackingSocket = new WebSocket(wsUrl);

    $('#liveStatusBadge').html('<i class="fa-solid fa-spinner fa-spin me-1"></i> Connecting...');

    trackingSocket.onopen = function() {
        $('#liveStatusBadge')
            .removeClass('bg-secondary bg-danger')
            .addClass('bg-success')
            .html('<i class="fa-solid fa-wifi me-1 animate-pulse"></i> WebSocket Live Stream Connected');
    };

    trackingSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);

        if (data.type === 'location_update' || data.type === 'bus_location_broadcast') {
            updateBusMarkerOnMap(data);
            updateTelemetryCard(data);
        } else if (data.type === 'initial_state' && data.bus_data) {
            updateBusMarkerOnMap(data.bus_data);
            updateTelemetryCard(data.bus_data);
        }
    };

    trackingSocket.onclose = function() {
        $('#liveStatusBadge')
            .removeClass('bg-success')
            .addClass('bg-warning text-dark')
            .html('<i class="fa-solid fa-wifi-slash me-1"></i> Reconnecting...');
        // Auto-reconnect after 3 seconds
        setTimeout(() => startBusTrackingSocket(busId), 3000);
    };

    trackingSocket.onerror = function(err) {
        console.error("WebSocket Error:", err);
    };
}

function updateTelemetryCard(data) {
    if ($('#telemetryCard').length) {
        $('#telBusNum').text(`Bus ${data.bus_number || data.bus_id}`);
        $('#telStatus').text(data.status || 'LIVE');
        $('#telSpeed').text(data.speed ? data.speed.toFixed(1) : '0.0');
        $('#telHeading').text(data.heading ? `${data.heading.toFixed(0)}°` : '0°');
        $('#telUpdated').text(new Date().toLocaleTimeString());
    }
}

function locatePassenger() {
    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(function(pos) {
            updatePassengerMarker(pos.coords.latitude, pos.coords.longitude);
        }, function(err) {
            alert("Could not retrieve GPS location.");
        });
    }
}
