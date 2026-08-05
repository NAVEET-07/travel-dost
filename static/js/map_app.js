/* Travel Dost Leaflet Map Core Helper */

let travelDostMap = null;
let busMarkersMap = {};
let passengerMarker = null;
let busStopMarkersGroup = null;

function initTravelDostMap(elementId, centerLat = 15.3647, centerLng = 75.1240, zoomLevel = 12) {
    if (travelDostMap) {
        travelDostMap.remove();
        travelDostMap = null;
        busMarkersMap = {};
    }

    travelDostMap = L.map(elementId).setView([centerLat, centerLng], zoomLevel);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Travel Dost'
    }).addTo(travelDostMap);

    busStopMarkersGroup = L.layerGroup().addTo(travelDostMap);

    return travelDostMap;
}

/**
 * Requirement 2 & 4: Live Bus Icon / Logo Only
 */
function createBusIcon(status = 'LIVE', busNumber = '') {
    const isLive = status === 'LIVE';
    const bgColor = isLive ? '#10b981' : '#64748b';

    return L.divIcon({
        className: 'custom-bus-div-icon',
        html: `
            <div class="bus-marker-wrapper">
                <div class="bus-marker-pin" style="background: ${bgColor}; border: 3px solid white;">
                    <i class="fa-solid fa-bus text-white"></i>
                </div>
                ${busNumber ? `<span class="bus-number-badge">${busNumber}</span>` : ''}
            </div>
        `,
        iconSize: [44, 44],
        iconAnchor: [22, 22],
        popupAnchor: [0, -22]
    });
}

/**
 * Requirement 2 & 4: Display bus stops using ONLY the green box design (.stop-marker-icon)
 * No extra polylines, circles, labels, or unnecessary decorations.
 */
function plotRouteStopsOnly(stopsArray) {
    if (!busStopMarkersGroup || !stopsArray) return;
    busStopMarkersGroup.clearLayers();

    const bounds = [];

    stopsArray.forEach((stop, idx) => {
        const lat = parseFloat(stop.latitude || stop.lat);
        const lng = parseFloat(stop.longitude || stop.lng);
        if (isNaN(lat) || isNaN(lng)) return;

        bounds.push([lat, lng]);

        const stopIcon = L.divIcon({
            className: 'custom-stop-div-icon',
            html: `<div class="stop-marker-icon"><i class="fa-solid fa-bus-simple"></i> ${stop.stop_name || stop.name}</div>`,
            iconSize: [140, 26],
            iconAnchor: [70, 13]
        });

        const marker = L.marker([lat, lng], { icon: stopIcon });
        marker.bindPopup(`
            <div class="p-2">
                <strong class="d-block text-dark fs-6">${stop.stop_name || stop.name}</strong>
                <small class="text-secondary d-block mb-2">${stop.area || 'Bus Stop'}</small>
                <div class="btn-group btn-group-sm w-100">
                    <a href="/find-route/?source=${stop.id}" class="btn btn-outline-primary rounded-start-pill">Board Here</a>
                    <a href="/find-route/?destination=${stop.id}" class="btn btn-outline-success rounded-end-pill">Alight Here</a>
                </div>
            </div>
        `);
        busStopMarkersGroup.addLayer(marker);
    });

    if (bounds.length > 0 && travelDostMap) {
        travelDostMap.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Clean pass-through for backwards compatibility
function plotSegmentedRouteOnMap(stopsArray) {
    plotRouteStopsOnly(stopsArray);
}

// Update Passenger GPS Marker
function updatePassengerMarker(lat, lng) {
    if (!travelDostMap) return;

    const passengerIcon = L.divIcon({
        className: 'custom-passenger-div-icon',
        html: `<div class="passenger-marker-icon"><i class="fa-solid fa-user"></i></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });

    if (passengerMarker) {
        passengerMarker.setLatLng([lat, lng]);
    } else {
        passengerMarker = L.marker([lat, lng], { icon: passengerIcon }).addTo(travelDostMap);
        passengerMarker.bindPopup("<strong>📍 Your Location</strong>");
    }

    travelDostMap.setView([lat, lng], 14);
}

/**
 * Requirement 3: Dynamic Real-time Bus Marker Movement
 * Smoothly updates bus position on map when WebSocket/API data arrives.
 * Handles offline buses cleanly.
 */
function updateBusMarkerOnMap(busData) {
    if (!travelDostMap || !busData) return;

    const busId = busData.bus_id || busData.id;
    const lat = parseFloat(busData.latitude);
    const lng = parseFloat(busData.longitude);
    const status = busData.status || busData.tracking_status || 'LIVE';
    const busNum = busData.bus_number || '';

    if (isNaN(lat) || isNaN(lng)) {
        // If location is invalid or bus goes offline completely, remove marker if exists
        if (status === 'OFFLINE' && busMarkersMap[busId]) {
            travelDostMap.removeLayer(busMarkersMap[busId]);
            delete busMarkersMap[busId];
        }
        return;
    }

    // Handle offline status
    if (status === 'OFFLINE') {
        if (busMarkersMap[busId]) {
            travelDostMap.removeLayer(busMarkersMap[busId]);
            delete busMarkersMap[busId];
        }
        return;
    }

    const nextStopName = busData.next_stop ? (busData.next_stop.name || busData.next_stop.stop_name) : 'In Transit';
    const speedStr = busData.speed !== undefined && busData.speed !== null ? Number(busData.speed).toFixed(1) : '30.0';

    const popupContent = `
        <div class="p-2" style="min-width: 200px;">
            <div class="d-flex align-items-center justify-content-between gap-2 mb-1">
                <strong class="text-primary fs-6"><i class="fa-solid fa-bus me-1"></i> Bus ${busNum}</strong>
                <span class="badge bg-success">LIVE</span>
            </div>
            <p class="m-0 small"><strong>Route:</strong> ${busData.route_name || 'NWKRTC Bus'}</p>
            <p class="m-0 small text-success"><strong>Next Stop:</strong> ${nextStopName}</p>
            <p class="m-0 small"><strong>Speed:</strong> ${speedStr} km/h</p>
            <small class="text-muted d-block mt-1">Updated: ${busData.timestamp ? new Date(busData.timestamp).toLocaleTimeString() : 'Live'}</small>
        </div>
    `;

    if (busMarkersMap[busId]) {
        // Smoothly set new position
        busMarkersMap[busId].setLatLng([lat, lng]);
        busMarkersMap[busId].setIcon(createBusIcon(status, busNum));
        if (busMarkersMap[busId].getPopup()) {
            busMarkersMap[busId].getPopup().setContent(popupContent);
        }
    } else {
        const marker = L.marker([lat, lng], { icon: createBusIcon(status, busNum) }).addTo(travelDostMap);
        marker.bindPopup(popupContent);
        busMarkersMap[busId] = marker;
    }
}
