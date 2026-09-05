/* Travel Dost WebSocket Tracking Handler & Fallback */

let trackingSocket = null;
let pollingIntervalId = null;
let currentTrackedBusId = null;

function startBusTrackingSocket(busId) {
    currentTrackedBusId = busId;

    if (trackingSocket) {
        try { trackingSocket.close(); } catch(e){}
        trackingSocket = null;
    }

    if (!busId || busId === 'none') {
        stopPollingFallback();
        return;
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = busId && busId !== 'all' 
        ? `${wsProtocol}${window.location.host}/ws/bus-tracking/${busId}/`
        : `${wsProtocol}${window.location.host}/ws/bus-tracking/`;

    try {
        trackingSocket = new WebSocket(wsUrl);

        $('#liveStatusBadge').html('<i class="fa-solid fa-spinner fa-spin me-1"></i> Connecting...');

        trackingSocket.onopen = function() {
            $('#liveStatusBadge')
                .removeClass('bg-secondary bg-danger bg-warning text-dark')
                .addClass('bg-success text-white')
                .html('<span class="live-dot me-1"></span> WebSocket Live');
            stopPollingFallback();
        };

        trackingSocket.onmessage = function(e) {
            const data = JSON.parse(e.data);

            if (data.type === 'location_update' || data.type === 'bus_location_broadcast') {
                if (data.status === 'OFFLINE') {
                    // Remove marker
                    updateBusMarkerOnMap({ bus_id: data.bus_id, status: 'OFFLINE' });
                    if (typeof window.onBusOffline === 'function') {
                        window.onBusOffline(data.bus_id);
                    }
                } else {
                    updateBusMarkerOnMap(data);
                    updateTelemetryCard(data);
                    if (typeof window.onBusLocationUpdate === 'function') {
                        window.onBusLocationUpdate(data);
                    }
                }
            } else if (data.type === 'initial_state') {
                if (data.bus_data && data.bus_data.status === 'LIVE') {
                    updateBusMarkerOnMap(data.bus_data);
                    updateTelemetryCard(data.bus_data);
                }
                if (data.buses_data && Array.isArray(data.buses_data)) {
                    data.buses_data.forEach(b => {
                        if (b.status === 'LIVE') {
                            updateBusMarkerOnMap(b);
                        }
                    });
                    if (data.buses_data.length > 0) {
                        updateTelemetryCard(data.buses_data[0]);
                    }
                }
            }
        };

        trackingSocket.onclose = function() {
            $('#liveStatusBadge')
                .removeClass('bg-success')
                .addClass('bg-warning text-dark')
                .html('<i class="fa-solid fa-satellite me-1"></i> Live REST Polling (5s)');
            
            startPollingFallback(busId);

            // Reconnect websocket after 5 seconds if bus selection hasn't changed
            setTimeout(() => {
                if (currentTrackedBusId === busId && (!trackingSocket || trackingSocket.readyState === WebSocket.CLOSED)) {
                    startBusTrackingSocket(busId);
                }
            }, 5000);
        };

        trackingSocket.onerror = function(err) {
            console.warn("WebSocket error, fallback to REST polling:", err);
            startPollingFallback(busId);
        };
    } catch(err) {
        console.warn("WebSocket init error, fallback to REST polling:", err);
        startPollingFallback(busId);
    }
}

function startPollingFallback(busId) {
    fetchBusesApi(busId);

    if (pollingIntervalId) clearInterval(pollingIntervalId);

    // Strictly poll at 5 seconds interval
    pollingIntervalId = setInterval(() => {
        fetchBusesApi(busId);
    }, 5000);
}

function stopPollingFallback() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

function fetchBusesApi(busId) {
    if (busId && busId !== 'all') {
        $.ajax({
            url: `/api/buses/${busId}/tracking-status/`,
            type: 'GET',
            success: function(resp) {
                if (resp && resp.is_live && resp.latest_location) {
                    const data = {
                        bus_id: resp.bus_id,
                        bus_number: resp.bus_number,
                        bus_name: resp.bus_name,
                        bus_type: resp.bus_type,
                        latitude: resp.latest_location.latitude,
                        longitude: resp.latest_location.longitude,
                        speed: resp.latest_location.speed,
                        heading: resp.latest_location.heading,
                        status: resp.tracking_status,
                        timestamp: resp.latest_location.timestamp
                    };
                    updateBusMarkerOnMap(data);
                    updateTelemetryCard(data);
                } else if (resp && !resp.is_live) {
                    // Remove if no longer live
                    updateBusMarkerOnMap({ bus_id: resp.bus_id, status: 'OFFLINE' });
                }
            }
        });
    } else {
        // Query strictly LIVE buses only
        $.ajax({
            url: `/api/buses/?status=LIVE`,
            type: 'GET',
            success: function(resp) {
                if (Array.isArray(resp)) {
                    resp.forEach(b => {
                        if (b.current_location && b.tracking_status === 'LIVE' && b.trip_status === 'IN_TRANSIT') {
                            const data = {
                                bus_id: b.id,
                                bus_number: b.bus_number,
                                bus_name: b.bus_name,
                                bus_type: b.bus_type_display,
                                latitude: b.current_location.latitude,
                                longitude: b.current_location.longitude,
                                speed: b.current_location.speed,
                                heading: b.current_location.heading,
                                status: b.tracking_status,
                                timestamp: b.current_location.timestamp
                            };
                            updateBusMarkerOnMap(data);
                        }
                    });
                }
            }
        });
    }
}

function updateTelemetryCard(data) {
    if ($('#telemetryCard').length && data) {
        if (data.bus_number) {
            $('#telBusNum').text(`Bus ${data.bus_number}`);
        }
        if (data.status) {
            $('#telStatus').text(data.status);
            if (data.status === 'LIVE') {
                $('#telStatus').removeClass('bg-secondary bg-danger').addClass('bg-success');
            } else {
                $('#telStatus').removeClass('bg-success').addClass('bg-secondary');
            }
        }
        if (data.speed !== undefined && data.speed !== null) {
            $('#telSpeed').text(Number(data.speed).toFixed(1));
        }
        if (data.heading !== undefined && data.heading !== null) {
            $('#telHeading').text(`${Math.round(data.heading)}°`);
        }
        $('#telUpdated').text('Live 5s');
    }
}
