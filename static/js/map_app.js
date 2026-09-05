/* Travel Dost Leaflet Map Core Helper */

let travelDostMap = null;
let busMarkersMap = {};
let passengerMarker = null;
let busStopMarkersGroup = null;
let traveledPolyline = null;
let remainingPolyline = null;
let approachingPolyline = null;

function initTravelDostMap(elementId, centerLat = 15.3647, centerLng = 75.1240, zoomLevel = 12) {
    if (travelDostMap) {
        travelDostMap.remove();
        travelDostMap = null;
        busMarkersMap = {};
        traveledPolyline = null;
        remainingPolyline = null;
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
 * Live Bus Marker Pin (Hubballi-Dharwad Smart Transit Theme)
 */
function createBusIcon(status = 'LIVE', busNumber = '', heading = 0) {
    const isLive = status === 'LIVE';
    const bgColor = isLive ? '#10b981' : '#64748b';
    const pulseClass = isLive ? 'pulse-active' : '';

    return L.divIcon({
        className: 'custom-bus-div-icon',
        html: `
            <div class="bus-marker-wrapper ${pulseClass}">
                <div class="bus-marker-pin" style="background: ${bgColor}; border: 3px solid #ffffff;">
                    <i class="fa-solid fa-bus text-white"></i>
                </div>
                ${busNumber ? `<span class="bus-number-badge">${busNumber}</span>` : ''}
            </div>
        `,
        iconSize: [46, 46],
        iconAnchor: [23, 23],
        popupAnchor: [0, -23]
    });
}

/**
 * Traveled (Start -> Bus) vs Remaining (Bus -> End) Route Visualizer
 * - Traveled Path: Solid Emerald Green (#10b981, weight 6)
 * - Remaining Path: Dashed Transit Blue (#2563eb, weight 5, dashArray: 6,8)
 */
function renderTraveledAndRemainingRoute(busLatLng, routeStops, traveledRoadPoints, remainingRoadPoints) {
    if (!travelDostMap) return;

    // Clear old route polylines
    if (traveledPolyline) {
        travelDostMap.removeLayer(traveledPolyline);
        traveledPolyline = null;
    }
    if (remainingPolyline) {
        travelDostMap.removeLayer(remainingPolyline);
        remainingPolyline = null;
    }

    const bounds = [];

    // 1. Draw Traveled Path (Solid Green)
    if (traveledRoadPoints && traveledRoadPoints.length >= 2) {
        traveledPolyline = L.polyline(traveledRoadPoints, {
            color: '#10b981',
            weight: 6,
            opacity: 0.95,
            lineJoin: 'round',
            lineCap: 'round'
        }).addTo(travelDostMap);
        traveledRoadPoints.forEach(p => bounds.push(p));
    }

    // 2. Draw Remaining Path (Dashed Blue)
    if (remainingRoadPoints && remainingRoadPoints.length >= 2) {
        remainingPolyline = L.polyline(remainingRoadPoints, {
            color: '#2563eb',
            weight: 5,
            opacity: 0.85,
            dashArray: '7, 8',
            lineJoin: 'round',
            lineCap: 'round'
        }).addTo(travelDostMap);
        remainingRoadPoints.forEach(p => bounds.push(p));
    }

    // Fallback: If no road points, connect stops directly
    if ((!traveledRoadPoints || traveledRoadPoints.length < 2) && routeStops && routeStops.length > 0) {
        plotRouteStopsOnly(routeStops);
    } else if (routeStops && routeStops.length > 0) {
        plotDetailedRouteStops(routeStops, busLatLng);
    }

    if (busLatLng) {
        bounds.push(busLatLng);
    }

    if (bounds.length > 0) {
        travelDostMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
}

/**
 * Plot route stops distinguishing Passed/Completed stops vs Upcoming stops
 */
function plotDetailedRouteStops(stopsArray, busLatLng) {
    if (!busStopMarkersGroup || !stopsArray) return;
    busStopMarkersGroup.clearLayers();

    stopsArray.forEach((stop, idx) => {
        const lat = parseFloat(stop.latitude || stop.lat);
        const lng = parseFloat(stop.longitude || stop.lng);
        if (isNaN(lat) || isNaN(lng)) return;

        const isPassed = stop.passed === true;
        const isFirst = idx === 0;
        const isLast = idx === stopsArray.length - 1;

        let iconHtml = '';
        if (isFirst) {
            iconHtml = `<div class="stop-marker-icon" style="background:#0f172a; border-color:#38bdf8;"><i class="fa-solid fa-play text-warning"></i> ${stop.name || stop.stop_name} (Origin)</div>`;
        } else if (isLast) {
            iconHtml = `<div class="stop-marker-icon" style="background:#0f172a; border-color:#ef4444;"><i class="fa-solid fa-flag-checkered text-danger"></i> ${stop.name || stop.stop_name} (Terminus)</div>`;
        } else if (isPassed) {
            iconHtml = `<div class="stop-marker-icon" style="background:#ecfdf5; color:#065f46; border-color:#10b981;"><i class="fa-solid fa-circle-check text-success"></i> ${stop.name || stop.stop_name}</div>`;
        } else {
            iconHtml = `<div class="stop-marker-icon" style="background:#ffffff; color:#1e293b; border-color:#2563eb;"><i class="fa-solid fa-clock text-primary"></i> ${stop.name || stop.stop_name} ${stop.eta_mins ? `<span class="badge bg-primary ms-1">${stop.eta_mins}m</span>` : ''}</div>`;
        }

        const stopIcon = L.divIcon({
            className: 'custom-stop-div-icon',
            html: iconHtml,
            iconSize: [160, 28],
            iconAnchor: [80, 14]
        });

        const marker = L.marker([lat, lng], { icon: stopIcon });
        marker.bindPopup(`
            <div class="p-2" style="min-width: 180px;">
                <span class="badge ${isPassed ? 'bg-success' : 'bg-primary'} mb-1">${isPassed ? 'Passed Stop' : 'Upcoming Stop'}</span>
                <strong class="d-block text-dark fs-6">${stop.name || stop.stop_name}</strong>
                <small class="text-secondary d-block mb-2">Stop #${idx + 1} • ${stop.area || 'Hubballi-Dharwad'}</small>
                ${stop.eta_mins ? `<p class="m-0 small text-primary fw-bold"><i class="fa-solid fa-hourglass-half me-1"></i> Estimated Arrival: ~${stop.eta_mins} mins</p>` : ''}
            </div>
        `);
        busStopMarkersGroup.addLayer(marker);
    });
}

function plotRouteStopsOnly(stopsArray) {
    plotDetailedRouteStops(stopsArray, null);
}

function plotSegmentedRouteOnMap(stopsArray) {
    plotRouteStopsOnly(stopsArray);
}

// Update Passenger GPS Marker
function updatePassengerMarker(lat, lng) {
    if (!travelDostMap) return;

    const passengerIcon = L.divIcon({
        className: 'custom-passenger-div-icon',
        html: `<div class="passenger-marker-icon" style="background: #ef4444; color: white; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(239, 68, 68, 0.4); border: 2px solid white;"><i class="fa-solid fa-person-walking"></i></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });

    if (passengerMarker) {
        passengerMarker.setLatLng([lat, lng]);
    } else {
        passengerMarker = L.marker([lat, lng], { icon: passengerIcon }).addTo(travelDostMap);
        passengerMarker.bindPopup("<strong>📍 Your Current Location</strong>");
    }

    travelDostMap.setView([lat, lng], 14);
}

/**
 * Real-Time Live Bus Marker Plotter
 * If status is OFFLINE, marker is immediately deleted from map.
 */
function updateBusMarkerOnMap(busData) {
    if (!travelDostMap || !busData) return;

    const busId = busData.bus_id || busData.id;
    const lat = parseFloat(busData.latitude);
    const lng = parseFloat(busData.longitude);
    const status = busData.status || busData.tracking_status || 'LIVE';
    const busNum = busData.bus_number || '';

    // If offline or invalid coordinates, remove marker completely
    if (isNaN(lat) || isNaN(lng) || status === 'OFFLINE') {
        if (busMarkersMap[busId]) {
            travelDostMap.removeLayer(busMarkersMap[busId]);
            delete busMarkersMap[busId];
        }
        return;
    }

    const speedStr = busData.speed !== undefined && busData.speed !== null ? Number(busData.speed).toFixed(1) : '30.0';

    const popupContent = `
        <div class="p-2" style="min-width: 210px;">
            <div class="d-flex align-items-center justify-content-between gap-2 mb-2">
                <strong class="text-primary fs-6"><i class="fa-solid fa-bus me-1"></i> Bus ${busNum}</strong>
                <span class="badge bg-success"><span class="live-dot me-1"></span> LIVE</span>
            </div>
            <p class="m-0 small"><strong>Route:</strong> ${busData.route_name || 'NWKRTC Service'}</p>
            <p class="m-0 small"><strong>Speed:</strong> ${speedStr} km/h</p>
            <p class="m-0 small text-muted"><strong>Updated:</strong> ${busData.timestamp ? new Date(busData.timestamp).toLocaleTimeString() : 'Live 5s GPS'}</p>
        </div>
    `;

    if (busMarkersMap[busId]) {
        busMarkersMap[busId].setLatLng([lat, lng]);
        busMarkersMap[busId].setIcon(createBusIcon(status, busNum, busData.heading || 0));
        if (busMarkersMap[busId].getPopup()) {
            busMarkersMap[busId].getPopup().setContent(popupContent);
        }
    } else {
        const marker = L.marker([lat, lng], { icon: createBusIcon(status, busNum, busData.heading || 0) }).addTo(travelDostMap);
        marker.bindPopup(popupContent);
        busMarkersMap[busId] = marker;
    }

    // Dynamically update traveled polyline end and remaining polyline start if they exist
    if (traveledPolyline && remainingPolyline) {
        const traveledPts = traveledPolyline.getLatLngs();
        if (traveledPts.length > 0) {
            traveledPts[traveledPts.length - 1] = L.latLng(lat, lng);
            traveledPolyline.setLatLngs(traveledPts);
        }
        const remainingPts = remainingPolyline.getLatLngs();
        if (remainingPts.length > 0) {
            remainingPts[0] = L.latLng(lat, lng);
            remainingPolyline.setLatLngs(remainingPts);
        }
    }
}
