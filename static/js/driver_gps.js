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

    driverMap = L.map('driverMap', {
        fadeAnimation: true,
        zoomAnimation: true
    }).setView([15.36470, 75.12400], 13);
    const osmTileUrl = window.osmTileUrl || 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
    const osmTileAttribution = window.osmTileAttribution || 'Tiles &copy; Esri &mdash; Sources: Esri, DeLorme, NAVTEQ, USGS, METI';

    const tileOptions = {
        maxZoom: 19,
        attribution: osmTileAttribution
    };
    L.tileLayer(osmTileUrl, tileOptions).addTo(driverMap);

    // Staggered invalidation passes to guarantee no blank/gray canvas
    setTimeout(() => { if (driverMap) driverMap.invalidateSize(true); }, 80);
    setTimeout(() => { if (driverMap) driverMap.invalidateSize(true); }, 250);
    setTimeout(() => { if (driverMap) driverMap.invalidateSize(true); }, 600);

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

    // Render ordered route stops and scheduled route path (Problem 3)
    if (window.routeStops && window.routeStops.length > 0) {
        const stopLatLngs = [];
        const boundsMarkers = [];

        window.routeStops.forEach((stop, idx) => {
            const lat = parseFloat(stop.lat);
            const lng = parseFloat(stop.lon || stop.lng);
            if (isNaN(lat) || isNaN(lng)) return;

            stopLatLngs.push([lat, lng]);
            const isFirst = idx === 0;
            const isLast = idx === window.routeStops.length - 1;

            const stopDivIcon = L.divIcon({
                className: 'driver-stop-divicon',
                html: `
                    <div style="background: ${isFirst ? '#10b981' : (isLast ? '#ef4444' : '#0284c7')}; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 11px; border: 2px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.35);">
                        ${stop.stop_order || (idx + 1)}
                    </div>
                `,
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });

            const stopMarker = L.marker([lat, lng], { icon: stopDivIcon }).addTo(driverMap)
                .bindPopup(`
                    <div style="padding: 4px;">
                        <span class="badge ${isFirst ? 'bg-success' : (isLast ? 'bg-danger' : 'bg-primary')} mb-1">
                            ${isFirst ? 'START STOP' : (isLast ? 'DESTINATION' : 'STOP #' + (stop.stop_order || (idx + 1)))}
                        </span>
                        <h6 style="margin: 0; font-weight: bold; color: #1e293b;">${stop.stop_name}</h6>
                        <small class="text-muted">${stop.area || ''} • ${(stop.distance_from_start_km || 0).toFixed(1)} km</small>
                    </div>
                `);

            boundsMarkers.push(stopMarker);
        });

        if (stopLatLngs.length >= 2) {
            // Draw planned scheduled route polyline in blue
            L.polyline(stopLatLngs, {
                color: '#2563eb',
                weight: 4,
                opacity: 0.8,
                dashArray: '5, 8',
                lineCap: 'round',
                lineJoin: 'round'
            }).addTo(driverMap);
        }

        if (boundsMarkers.length > 0) {
            const group = L.featureGroup(boundsMarkers);
            if (group.getBounds().isValid()) {
                driverMap.fitBounds(group.getBounds(), { padding: [35, 35] });
            }
        }
    }
}

window.centerDriverMapOnStop = function(lat, lng, name) {
    if (!driverMap) return;
    driverMap.setView([lat, lng], 16, { animate: true });
    driverMap.eachLayer(function(layer) {
        if (layer.getLatLng) {
            const ll = layer.getLatLng();
            if (Math.abs(ll.lat - lat) < 0.0001 && Math.abs(ll.lng - lng) < 0.0001) {
                layer.openPopup();
            }
        }
    });
};

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
    nextSyncCountdown = 2;
    updateCountdownUI();

    countdownIntervalId = setInterval(function() {
        nextSyncCountdown--;
        if (nextSyncCountdown <= 0) {
            nextSyncCountdown = 2;
        }
        updateCountdownUI();
    }, 1000);
}

function updateCountdownUI() {
    $('#gpsCountdown').html(`<i class="fa-solid fa-satellite-dish me-1 text-warning"></i> Next GPS sync in <strong>${nextSyncCountdown}s</strong>`);
}

let lastGpsBroadcastTime = 0;
const GPS_BROADCAST_INTERVAL_MS = 2000; // Strict 2-second interval

function sendGpsPayload(lat, lng, speed, heading) {
    const now = Date.now();
    lastGpsBroadcastTime = now;
    packetsSentCount++;
    nextSyncCountdown = 2;
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

let driverWatchPositionId = null;

function startBrowserGpsTracking() {
    if ("geolocation" in navigator) {
        const geoOptions = {
            enableHighAccuracy: true,
            timeout: 2000,
            maximumAge: 0
        };

        // 1. Immediate initial transmission
        navigator.geolocation.getCurrentPosition(
            function(position) {
                processAndSendPosition(position);
            },
            function(err) {
                console.warn("Initial GPS error, switching to route waypoints simulation:", err);
                startSimulationMode();
            },
            geoOptions
        );

        // 2. High-frequency watchPosition throttled to strict 2000ms cadence
        if (driverWatchPositionId !== null) {
            navigator.geolocation.clearWatch(driverWatchPositionId);
        }
        driverWatchPositionId = navigator.geolocation.watchPosition(
            function(position) {
                const now = Date.now();
                if (now - lastGpsBroadcastTime >= (GPS_BROADCAST_INTERVAL_MS - 150)) {
                    processAndSendPosition(position);
                }
            },
            function(err) {
                console.warn("watchPosition GPS error:", err);
            },
            geoOptions
        );

        // 3. Strict 2-second heartbeat interval (guarantees pings every 2000ms even if static)
        if (geoIntervalId) clearInterval(geoIntervalId);
        geoIntervalId = setInterval(function() {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const now = Date.now();
                    if (now - lastGpsBroadcastTime >= (GPS_BROADCAST_INTERVAL_MS - 200)) {
                        processAndSendPosition(position);
                    }
                },
                function(err) {
                    console.warn("Interval 2s GPS poll error:", err);
                },
                geoOptions
            );
        }, GPS_BROADCAST_INTERVAL_MS);
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

    // Broadcast route waypoint location update every 2 seconds (2000ms)
    simIntervalId = setInterval(function() {
        simIndex = (simIndex + 1) % waypoints.length;
        const wp = waypoints[simIndex];
        sendGpsPayload(wp.lat, wp.lng, wp.speed || 35.0, wp.heading || 90);
    }, GPS_BROADCAST_INTERVAL_MS);
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
