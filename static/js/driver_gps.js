/* Travel Dost Driver GPS Transmitter & Map Preview */

let driverSocket = null;
let geoIntervalId = null;
let simIntervalId = null;
let currentTrackingBusId = null;
let driverMap = null;
let driverMarker = null;

// Route Waypoints for Viva/Demo simulation (KLEIT -> Vidya Nagar -> Unkal Lake -> Navanagar -> Rayapur -> Sattur -> Dharwad CBT)
const simWaypoints = [
    { lat: 15.36470, lng: 75.12400, speed: 28.5, heading: 180 }, // KLEIT
    { lat: 15.36800, lng: 75.12200, speed: 32.0, heading: 195 },
    { lat: 15.37300, lng: 75.11800, speed: 35.5, heading: 210 },
    { lat: 15.37800, lng: 75.11500, speed: 40.0, heading: 220 }, // Unkal Lake
    { lat: 15.38800, lng: 75.10200, speed: 45.0, heading: 230 },
    { lat: 15.40100, lng: 75.08900, speed: 48.0, heading: 240 }, // Navanagar
    { lat: 15.41200, lng: 75.07500, speed: 50.0, heading: 250 }, // Rayapur
    { lat: 15.42500, lng: 75.04500, speed: 42.0, heading: 260 }, // SDM Sattur
    { lat: 15.44200, lng: 75.02000, speed: 38.0, heading: 270 },
    { lat: 15.45800, lng: 75.00800, speed: 25.0, heading: 280 }  // Dharwad CBT
];
let simIndex = 0;

$(document.body).ready(function() {
    initDriverMap();

    $('#btnStartTrip').on('click', function() {
        const busId = $('#driverBusId').val();
        if (!busId) {
            alert("No assigned bus found to start trip.");
            return;
        }

        currentTrackingBusId = busId;
        const isSimMode = $('#simToggle').is(':checked');

        initDriverSocket(busId, function() {
            if (isSimMode) {
                startSimulationMode();
            } else {
                startBrowserGpsTracking();
            }

            $('#btnStartTrip').addClass('d-none');
            $('#btnStopTrip').removeClass('d-none');
            $('#simToggle').prop('disabled', true);
            $('#driverStatusBadge')
                .removeClass('bg-secondary bg-danger')
                .addClass('bg-success')
                .html('<i class="fa-solid fa-signal me-1 animate-pulse"></i> LIVE TRIP ACTIVE');
            $('#telemetryStatus').text('LIVE TRIP ACTIVE').removeClass('text-warning').addClass('text-success');
        });
    });

    $('#btnStopTrip').on('click', function() {
        stopTrip();
    });
});

function initDriverMap() {
    if ($('#driverMap').length === 0) return;

    driverMap = L.map('driverMap').setView([15.36470, 75.12400], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(driverMap);

    const busIcon = L.divIcon({
        className: 'custom-bus-icon',
        html: `<div style="background: #2563eb; color: white; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 2px solid white;">
                <i class="fa-solid fa-bus" style="font-size: 16px;"></i>
               </div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });

    driverMarker = L.marker([15.36470, 75.12400], { icon: busIcon }).addTo(driverMap)
        .bindPopup("<b>Your Assigned Bus</b><br>Location telemetry active.")
        .openPopup();
}

function initDriverSocket(busId, callback) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = `${wsProtocol}${window.location.host}/ws/bus-tracking/${busId}/`;

    try {
        driverSocket = new WebSocket(wsUrl);

        driverSocket.onopen = function() {
            console.log("Driver WebSocket connected for Bus", busId);
            if (callback) callback();
        };

        driverSocket.onerror = function(err) {
            console.warn("Driver WebSocket Error, fallback to REST API:", err);
            if (callback) callback();
        };

        driverSocket.onclose = function() {
            console.log("Driver WebSocket closed");
        };
    } catch (e) {
        console.warn("WebSocket setup failed, using REST endpoint fallback:", e);
        if (callback) callback();
    }
}

function sendGpsPayload(lat, lng, speed, heading) {
    const payload = {
        action: 'location_update',
        bus_id: currentTrackingBusId,
        latitude: lat,
        longitude: lng,
        speed: speed || 0.0,
        heading: heading || 0.0,
        status: 'LIVE'
    };

    // Send over WebSocket if open
    if (driverSocket && driverSocket.readyState === WebSocket.OPEN) {
        driverSocket.send(JSON.stringify(payload));
    }

    // Always post REST fallback to update DB
    $.ajax({
        url: `/api/buses/${currentTrackingBusId}/location/`,
        type: 'POST',
        data: JSON.stringify(payload),
        contentType: 'application/json'
    });

    // Update telemetry UI
    $('#gpsLat').text(lat.toFixed(6));
    $('#gpsLng').text(lng.toFixed(6));
    $('#gpsSpeed').text(`${(speed || 0).toFixed(1)} km/h`);
    $('#gpsLastSent').text(new Date().toLocaleTimeString());

    // Update map marker
    if (driverMap && driverMarker) {
        const newLatLng = new L.LatLng(lat, lng);
        driverMarker.setLatLng(newLatLng);
        driverMap.panTo(newLatLng);
    }
}

function startBrowserGpsTracking() {
    if ("geolocation" in navigator) {
        // Send initial location
        navigator.geolocation.getCurrentPosition(
            function(position) {
                processAndSendPosition(position);
            },
            function(err) {
                alert("Browser Geolocation Error: " + err.message + "\nSwitching to Viva Simulation Mode.");
                startSimulationMode();
            },
            { enableHighAccuracy: true }
        );

        // Continuously send GPS location every 5 seconds
        if (geoIntervalId) clearInterval(geoIntervalId);
        geoIntervalId = setInterval(function() {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    processAndSendPosition(position);
                },
                function(err) {
                    console.warn("Interval location error:", err);
                },
                { enableHighAccuracy: true, timeout: 4000 }
            );
        }, 5000); // 5 seconds continuous location updates
    } else {
        alert("Browser does not support Geolocation. Switching to Simulation Mode.");
        startSimulationMode();
    }
}

function processAndSendPosition(position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    const speed = (position.coords.speed || 0) * 3.6; // convert m/s to km/h
    const heading = position.coords.heading || 0.0;
    sendGpsPayload(lat, lng, speed, heading);
}

function startSimulationMode() {
    if (simIntervalId) clearInterval(simIntervalId);

    const waypoints = (window.routeWaypoints && window.routeWaypoints.length > 0) ? window.routeWaypoints : simWaypoints;

    simIndex = 0;
    const wpInitial = waypoints[0];
    sendGpsPayload(wpInitial.lat, wpInitial.lng, wpInitial.speed || 35.0, wpInitial.heading || 90);

    simIntervalId = setInterval(function() {
        simIndex = (simIndex + 1) % waypoints.length;
        const wp = waypoints[simIndex];
        sendGpsPayload(wp.lat, wp.lng, wp.speed || 35.0, wp.heading || 90);
    }, 5000); // broadcast location update every 5 seconds
}


function stopTrip() {
    if (geoIntervalId) {
        clearInterval(geoIntervalId);
        geoIntervalId = null;
    }

    if (simIntervalId) {
        clearInterval(simIntervalId);
        simIntervalId = null;
    }

    if (driverSocket) {
        driverSocket.close();
        driverSocket = null;
    }

    // Mark bus offline via API
    if (currentTrackingBusId) {
        $.ajax({
            url: `/api/buses/${currentTrackingBusId}/location/`,
            type: 'POST',
            data: JSON.stringify({
                bus_id: currentTrackingBusId,
                latitude: parseFloat($('#gpsLat').text()) || 15.36470,
                longitude: parseFloat($('#gpsLng').text()) || 75.12400,
                status: 'OFFLINE'
            }),
            contentType: 'application/json'
        });
    }

    $('#btnStartTrip').removeClass('d-none');
    $('#btnStopTrip').addClass('d-none');
    $('#simToggle').prop('disabled', false);
    $('#driverStatusBadge')
        .removeClass('bg-success')
        .addClass('bg-secondary')
        .html('<i class="fa-solid fa-power-off me-1"></i> STANDBY');
    $('#telemetryStatus').text('STANDBY').removeClass('text-success').addClass('text-warning');
}
