/* Travel Dost Driver GPS Transmitter & Telemetry Cockpit
   - High-accuracy GPS polling every 3 seconds (3000ms)
   - Real-time breadcrumbs polyline on driver preview map
   - Live WebSocket + REST telemetry streaming
*/

let driverSocket = null;
let geoIntervalId = null;
let simIntervalId = null;
let countdownIntervalId = null;
let currentTrackingBusId = null;
let driverMap = null;
let driverMarker = null;
let driverTraveledPolyline = null;
let packetsSentCount = 0;
let nextSyncCountdown = 3;

// Hubballi-Dharwad Twin Cities Transit Corridors fallback if no stops assigned
const defaultCorridorWaypoints = [
    { lat: 15.36470, lng: 75.12400, speed: 28.5, heading: 180 }, // CBT Hubballi
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

        // Step 1: Explicitly notify backend that Trip is ACTIVE and bus is LIVE
        $.ajax({
            url: '/api/driver/trip/start/',
            type: 'POST',
            data: JSON.stringify({ bus_no: busId, bus_id: busId }),
            contentType: 'application/json',
            success: function(response) {
                console.log("Trip started on backend:", response);

                // Step 2: Establish WebSocket Connection
                initDriverSocket(busId, function() {
                    // Step 3: Start 3-second interval tracking
                    if (isSimMode) {
                        startSimulationMode();
                    } else {
                        startBrowserGpsTracking();
                    }

                    startCountdownTicker();

                    $('#btnStartTrip').addClass('d-none');
                    $('#btnStopTrip').removeClass('d-none');
                    $('#simToggle').prop('disabled', true);
                    $('#busSelectDropdown').prop('disabled', true);
                    $('#driverStatusBadge')
                        .removeClass('bg-secondary bg-danger')
                        .addClass('bg-success')
                        .html('<span class="live-dot me-1"></span> LIVE TRIP ACTIVE');
                    $('#telemetryStatus').text('ACTIVE (LIVE)').removeClass('text-warning text-secondary').addClass('text-success');
                });
            },
            error: function(xhr) {
                console.warn("REST start trip error, proceeding with socket:", xhr);
                initDriverSocket(busId, function() {
                    if (isSimMode) {
                        startSimulationMode();
                    } else {
                        startBrowserGpsTracking();
                    }
                    startCountdownTicker();

                    $('#btnStartTrip').addClass('d-none');
                    $('#btnStopTrip').removeClass('d-none');
                    $('#simToggle').prop('disabled', true);
                    $('#busSelectDropdown').prop('disabled', true);
                    $('#driverStatusBadge')
                        .removeClass('bg-secondary bg-danger')
                        .addClass('bg-success')
                        .html('<span class="live-dot me-1"></span> LIVE TRIP ACTIVE');
                    $('#telemetryStatus').text('ACTIVE (LIVE)').removeClass('text-warning text-secondary').addClass('text-success');
                });
            }
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
        attribution: '&copy; OpenStreetMap | Travel Dost'
    }).addTo(driverMap);

    const busIcon = L.divIcon({
        className: 'custom-bus-icon',
        html: `<div style="background: #10b981; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 14px rgba(16,185,129,0.55); border: 3px solid white;">
                <i class="fa-solid fa-bus" style="font-size: 18px;"></i>
               </div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20]
    });

    driverMarker = L.marker([15.36470, 75.12400], { icon: busIcon }).addTo(driverMap)
        .bindPopup("<b>Your Assigned Bus</b><br>3-second GPS telemetry active.")
        .openPopup();

    // Active traveled breadcrumbs polyline on driver cockpit map
    driverTraveledPolyline = L.polyline([], {
        color: '#10b981',
        weight: 5,
        opacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round'
    }).addTo(driverMap);
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

function startCountdownTicker() {
    if (countdownIntervalId) clearInterval(countdownIntervalId);
    nextSyncCountdown = 3;
    updateCountdownUI();

    countdownIntervalId = setInterval(function() {
        nextSyncCountdown--;
        if (nextSyncCountdown <= 0) {
            nextSyncCountdown = 3;
        }
        updateCountdownUI();
    }, 1000);
}

function updateCountdownUI() {
    $('#gpsCountdown').html(`<i class="fa-solid fa-satellite-dish me-1 text-warning"></i> Next GPS sync in <strong>${nextSyncCountdown}s</strong>`);
}

function sendGpsPayload(lat, lng, speed, heading) {
    packetsSentCount++;
    nextSyncCountdown = 3;
    updateCountdownUI();

    const timestampIso = new Date().toISOString();
    const payload = {
        action: 'location_update',
        bus_id: currentTrackingBusId,
        bus_no: currentTrackingBusId,
        latitude: lat,
        longitude: lng,
        lat: lat,
        lon: lng,
        speed: speed || 0.0,
        heading: heading || 0.0,
        timestamp: timestampIso,
        status: 'LIVE',
        trip_status: 'ACTIVE'
    };

    // 1. Send via WebSocket
    if (driverSocket && driverSocket.readyState === WebSocket.OPEN) {
        driverSocket.send(JSON.stringify(payload));
    }

    // 2. Send via REST endpoint to guarantee DB persistence
    $.ajax({
        url: '/api/driver/trip/update-location/',
        type: 'POST',
        data: JSON.stringify(payload),
        contentType: 'application/json',
        error: function() {
            // Fallback
            $.ajax({
                url: `/api/buses/${currentTrackingBusId}/location/`,
                type: 'POST',
                data: JSON.stringify(payload),
                contentType: 'application/json'
            });
        }
    });

    // 3. Update Cockpit Telemetry UI
    $('#gpsLat').text(lat.toFixed(6));
    $('#gpsLng').text(lng.toFixed(6));
    $('#gpsSpeed').text(Math.round(speed || 0));
    $('#gpsLastSent').text(new Date().toLocaleTimeString());
    $('#gpsPacketCount').html(`<i class="fa-solid fa-signal me-1 text-success"></i> Pings: <strong>${packetsSentCount}</strong>`);

    // 4. Update driver preview map & append traveled breadcrumb
    if (driverMap && driverMarker) {
        const newLatLng = new L.LatLng(lat, lng);
        driverMarker.setLatLng(newLatLng);
        if (driverTraveledPolyline) {
            driverTraveledPolyline.addLatLng(newLatLng);
        }
        driverMap.panTo(newLatLng);
    }
}

function startBrowserGpsTracking() {
    if ("geolocation" in navigator) {
        // Immediate initial transmission
        navigator.geolocation.getCurrentPosition(
            function(position) {
                processAndSendPosition(position);
            },
            function(err) {
                console.warn("Initial GPS error, switching to route waypoints simulation:", err);
                startSimulationMode();
            },
            { enableHighAccuracy: true, timeout: 2800, maximumAge: 0 }
        );

        // Continuous high-accuracy transmission every 3,000 milliseconds (3 seconds)
        if (geoIntervalId) clearInterval(geoIntervalId);
        geoIntervalId = setInterval(function() {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    processAndSendPosition(position);
                },
                function(err) {
                    console.warn("Interval 3s GPS poll error:", err);
                },
                { enableHighAccuracy: true, timeout: 2800, maximumAge: 0 }
            );
        }, 3000);
    } else {
        alert("Browser does not support Geolocation. Switching to route waypoints mode.");
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

    const waypoints = (window.routeWaypoints && window.routeWaypoints.length > 0) ? window.routeWaypoints : defaultCorridorWaypoints;

    simIndex = 0;
    const wpInitial = waypoints[0];
    sendGpsPayload(wpInitial.lat, wpInitial.lng, wpInitial.speed || 35.0, wpInitial.heading || 90);

    // Broadcast route waypoint location update every 3 seconds (3000ms)
    simIntervalId = setInterval(function() {
        simIndex = (simIndex + 1) % waypoints.length;
        const wp = waypoints[simIndex];
        sendGpsPayload(wp.lat, wp.lng, wp.speed || 35.0, wp.heading || 90);
    }, 3000);
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

    if (countdownIntervalId) {
        clearInterval(countdownIntervalId);
        countdownIntervalId = null;
    }

    // Explicitly notify backend and WebSockets that Trip has COMPLETED and bus is OFFLINE
    if (currentTrackingBusId) {
        if (driverSocket && driverSocket.readyState === WebSocket.OPEN) {
            driverSocket.send(JSON.stringify({
                action: 'trip_end',
                bus_id: currentTrackingBusId,
                status: 'OFFLINE',
                trip_status: 'COMPLETED'
            }));
            driverSocket.close();
            driverSocket = null;
        }

        $.ajax({
            url: '/api/driver/trip/end/',
            type: 'POST',
            data: JSON.stringify({ bus_no: currentTrackingBusId, bus_id: currentTrackingBusId }),
            contentType: 'application/json'
        });
    }

    if (driverTraveledPolyline) {
        driverTraveledPolyline.setLatLngs([]);
    }

    $('#btnStartTrip').removeClass('d-none');
    $('#btnStopTrip').addClass('d-none');
    $('#simToggle').prop('disabled', false);
    $('#busSelectDropdown').prop('disabled', false);
    $('#driverStatusBadge')
        .removeClass('bg-success')
        .addClass('bg-secondary')
        .html('<i class="fa-solid fa-power-off me-1"></i> STANDBY');
    $('#telemetryStatus').text('STANDBY (OFFLINE)').removeClass('text-success').addClass('text-warning');
    $('#gpsSpeed').text('0');
    $('#gpsCountdown').html('<i class="fa-solid fa-clock me-1"></i> Sync every 3.0s');
}
