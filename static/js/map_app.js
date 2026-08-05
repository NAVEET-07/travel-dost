/* Travel Dost Leaflet Map Core Helper */

let travelDostMap = null;
let busMarkersMap = {};
let passengerMarker = null;
let busStopMarkersGroup = null;
let approachingPolyline = null;

function initTravelDostMap(elementId, centerLat = 15.3647, centerLng = 75.1240, zoomLevel = 12) {
    if (travelDostMap) {
        travelDostMap.remove();
        travelDostMap = null;
        busMarkersMap = {};
        approachingPolyline = null;
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
 * Rule 3 & 4: Live Bus Icon / Logo Only
 * Map-aligned visualization like Google Maps
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
 * Rule 1 & 4: Display bus stops using ONLY the green box design (.stop-marker-icon)
 * No extra clutter, no dynamic segment splitting unless transfers are required.
 */
function plotRouteStopsOnly(stopsArray) {
    if (!busStopMarkersGroup || !stopsArray) return;
    busStopMarkersGroup.clearLayers();

    const bounds = [];

    stopsArray.forEach((stop) => {
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

// Pass-through alias
function plotSegmentedRouteOnMap(stopsArray) {
    plotRouteStopsOnly(stopsArray);
}

/**
 * Rule 3: Progress line shrinks as bus approaches boarding stop
 */
function updateApproachingProgressLine(busLatLng, boardingStopLatLng) {
    if (!travelDostMap) return;

    if (!busLatLng || !boardingStopLatLng) {
        if (approachingPolyline) {
            travelDostMap.removeLayer(approachingPolyline);
            approachingPolyline = null;
        }
        return;
    }

    const dist = Math.hypot(busLatLng[0] - boardingStopLatLng[0], busLatLng[1] - boardingStopLatLng[1]);
    
    // If bus is within 50 meters of boarding stop, clear line
    if (dist < 0.0005) {
        if (approachingPolyline) {
            travelDostMap.removeLayer(approachingPolyline);
            approachingPolyline = null;
        }
        return;
    }

    if (approachingPolyline) {
        approachingPolyline.setLatLngs([busLatLng, boardingStopLatLng]);
    } else {
        approachingPolyline = L.polyline([busLatLng, boardingStopLatLng], {
            color: '#06b6d4',
            weight: 5,
            opacity: 0.8,
            dashArray: '8, 8',
            lineCap: 'round'
        }).addTo(travelDostMap);
    }
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
 * Rule 3 & 4: Live Real-Time Driver GPS Tracking (No Simulation)
 * Streams driver's device location -> server -> user map.
 */
function updateBusMarkerOnMap(busData) {
    if (!travelDostMap || !busData) return;

    const busId = busData.bus_id || busData.id;
    const lat = parseFloat(busData.latitude);
    const lng = parseFloat(busData.longitude);
    const status = busData.status || busData.tracking_status || 'LIVE';
    const busNum = busData.bus_number || '';

    if (isNaN(lat) || isNaN(lng) || status === 'OFFLINE') {
        if (busMarkersMap[busId]) {
            travelDostMap.removeLayer(busMarkersMap[busId]);
            delete busMarkersMap[busId];
        }
        return;
    }

    const speedStr = busData.speed !== undefined && busData.speed !== null ? Number(busData.speed).toFixed(1) : '30.0';

    const popupContent = `
        <div class="p-2" style="min-width: 200px;">
            <div class="d-flex align-items-center justify-content-between gap-2 mb-1">
                <strong class="text-primary fs-6"><i class="fa-solid fa-bus me-1"></i> Bus ${busNum}</strong>
                <span class="badge bg-success">LIVE</span>
            </div>
            <p class="m-0 small"><strong>Route:</strong> ${busData.route_name || 'NWKRTC Bus'}</p>
            <p class="m-0 small"><strong>Speed:</strong> ${speedStr} km/h</p>
            <small class="text-muted d-block mt-1">Updated: ${busData.timestamp ? new Date(busData.timestamp).toLocaleTimeString() : 'Live GPS'}</small>
        </div>
    `;

    if (busMarkersMap[busId]) {
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

    // Update approaching line if boarding stop coordinates provided
    if (busData.boarding_stop_lat && busData.boarding_stop_lng) {
        updateApproachingProgressLine([lat, lng], [parseFloat(busData.boarding_stop_lat), parseFloat(busData.boarding_stop_lng)]);
    }
}
