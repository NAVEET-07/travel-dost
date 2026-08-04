/* Travel Dost Leaflet Map Core Helper */

let travelDostMap = null;
let busMarkersMap = {};
let passengerMarker = null;
let busStopMarkersGroup = null;
let routePolylineGroup = null;

function initTravelDostMap(elementId, centerLat = 15.3647, centerLng = 75.1240, zoomLevel = 12) {
    if (travelDostMap) {
        travelDostMap.remove();
    }

    travelDostMap = L.map(elementId).setView([centerLat, centerLng], zoomLevel);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Travel Dost'
    }).addTo(travelDostMap);

    busStopMarkersGroup = L.layerGroup().addTo(travelDostMap);
    routePolylineGroup = L.layerGroup().addTo(travelDostMap);

    return travelDostMap;
}

// Custom Bus Marker (Blue circle with bus icon)
function createBusIcon(status = 'LIVE') {
    const color = status === 'LIVE' ? '#2563eb' : '#64748b';
    return L.divIcon({
        className: 'custom-bus-div-icon',
        html: `<div class="bus-marker-icon" style="background: ${color};"><i class="fa-solid fa-bus"></i></div>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -18]
    });
}

// Custom Passenger Marker (Red circle with user icon)
function createPassengerIcon() {
    return L.divIcon({
        className: 'custom-passenger-div-icon',
        html: `<div class="passenger-marker-icon"><i class="fa-solid fa-user"></i></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -17]
    });
}

// Plot Bus Stop Markers
function plotBusStops(stopsArray) {
    if (!busStopMarkersGroup) return;
    busStopMarkersGroup.clearLayers();

    stopsArray.forEach(stop => {
        const stopIcon = L.divIcon({
            className: 'custom-stop-div-icon',
            html: `<div class="stop-marker-icon"><i class="fa-solid fa-bus-simple me-1"></i> ${stop.stop_name || stop.name}</div>`,
            iconSize: [120, 24],
            iconAnchor: [60, 12]
        });

        const marker = L.marker([stop.latitude || stop.lat, stop.longitude || stop.lng], { icon: stopIcon });
        marker.bindPopup(`
            <div class="p-1">
                <strong class="d-block text-primary">${stop.stop_name || stop.name}</strong>
                <small class="text-secondary">${stop.area || ''}</small>
                <a href="/find-route/?source=${stop.id}" class="btn btn-xs btn-primary text-white d-block mt-2 rounded-pill">Select as Source Stop</a>
            </div>
        `);
        busStopMarkersGroup.addLayer(marker);
    });
}

// Update Passenger GPS Marker
function updatePassengerMarker(lat, lng) {
    if (!travelDostMap) return;

    if (passengerMarker) {
        passengerMarker.setLatLng([lat, lng]);
    } else {
        passengerMarker = L.marker([lat, lng], { icon: createPassengerIcon() }).addTo(travelDostMap);
        passengerMarker.bindPopup("<strong>📍 You Are Here</strong><br><small>Passenger Current Location</small>");
    }

    travelDostMap.setView([lat, lng], 14);
}

// Update or add moving Bus Marker
function updateBusMarkerOnMap(busData) {
    if (!travelDostMap || !busData) return;

    const busId = busData.bus_id;
    const lat = parseFloat(busData.latitude);
    const lng = parseFloat(busData.longitude);
    const status = busData.status || 'LIVE';

    if (isNaN(lat) || isNaN(lng)) return;

    const popupContent = `
        <div class="p-2">
            <div class="d-flex align-items-center justify-content-between gap-2 mb-1">
                <strong class="text-primary fs-6">Bus ${busData.bus_number || busId}</strong>
                <span class="badge ${status === 'LIVE' ? 'bg-success' : 'bg-secondary'}">${status}</span>
            </div>
            <p class="m-0 small"><strong>Name:</strong> ${busData.bus_name || 'NWKRTC Bus'}</p>
            <p class="m-0 small"><strong>Speed:</strong> ${busData.speed !== undefined && busData.speed !== null ? Number(busData.speed).toFixed(1) : 0} km/h</p>
            <small class="text-muted d-block mt-1">Last Updated: ${busData.timestamp ? new Date(busData.timestamp).toLocaleTimeString() : 'Just now'}</small>
        </div>
    `;

    if (busMarkersMap[busId]) {
        // Smoothly animate marker position shift
        busMarkersMap[busId].setLatLng([lat, lng]);
        busMarkersMap[busId].setIcon(createBusIcon(status));
        busMarkersMap[busId].getPopup().setContent(popupContent);
    } else {
        const marker = L.marker([lat, lng], { icon: createBusIcon(status) }).addTo(travelDostMap);
        marker.bindPopup(popupContent);
        busMarkersMap[busId] = marker;
    }
}
