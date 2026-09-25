/* Travel Dost Leaflet Map Core Helper */

let travelDostMap = null;
let busMarkersMap = {};
let passengerMarker = null;
let busStopMarkersGroup = null;
let traveledPolyline = null;
let remainingPolyline = null;
let approachingPolyline = null;
let sourceToDestPolyline = null; // Polyline 1: Source to Destination (One Type - Solid Vibrant Blue)
let busToSourcePolyline = null;  // Polyline 2: Bus Location to Source (Different Type - Dashed Amber)
let currentSourceStopCoords = null;
let currentDestStopCoords = null;

function calculateHaversineDistanceKm(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

function initTravelDostMap(elementId, centerLat = 15.3647, centerLng = 75.1240, zoomLevel = 12) {
    if (travelDostMap) {
        travelDostMap.remove();
        travelDostMap = null;
        busMarkersMap = {};
        traveledPolyline = null;
        remainingPolyline = null;
        approachingPolyline = null;
        sourceToDestPolyline = null;
        busToSourcePolyline = null;
        currentSourceStopCoords = null;
        currentDestStopCoords = null;
    }

    const mapElement = document.getElementById(elementId);
    if (!mapElement) return null;

    travelDostMap = L.map(elementId, {
        fadeAnimation: true,
        zoomAnimation: true
    }).setView([centerLat, centerLng], zoomLevel);

    const defaultTileUrl = window.osmTileUrl || 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png';
    const defaultAttribution = window.osmTileAttribution || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles style by <a href="https://www.hotosm.org/" target="_blank">Humanitarian OpenStreetMap Team</a>';
    const tileOptions = {
        maxZoom: 19,
        subdomains: window.osmTileSubdomains || 'abc',
        attribution: defaultAttribution
    };

    const primaryTileLayer = L.tileLayer(defaultTileUrl, tileOptions).addTo(travelDostMap);

    busStopMarkersGroup = L.layerGroup().addTo(travelDostMap);

    // Staggered invalidation passes to guarantee no blank/gray canvas
    const invalidate = () => { if (travelDostMap) travelDostMap.invalidateSize(true); };
    setTimeout(invalidate, 80);
    setTimeout(invalidate, 250);
    setTimeout(invalidate, 600);
    setTimeout(invalidate, 1200);
    window.addEventListener('resize', invalidate);

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
 * Render Tracking Polylines:
 * 1. Source to Destination: ONE TYPE (Solid Vibrant Electric Blue #2563eb, weight 6, opacity 0.92)
 * 2. Bus Location to Source: DIFFERENT TYPE (Dashed Amber Gold #f59e0b, weight 4.5, dashArray: 8, 10)
 */
function renderTrackingPolylines(busLatLng, routeStops, roadGeometry, traveledRoadPoints, remainingRoadPoints, breadcrumbsPoints) {
    if (!travelDostMap) return;

    // Clear old route polylines
    if (sourceToDestPolyline) {
        travelDostMap.removeLayer(sourceToDestPolyline);
        sourceToDestPolyline = null;
    }
    if (busToSourcePolyline) {
        travelDostMap.removeLayer(busToSourcePolyline);
        busToSourcePolyline = null;
    }
    if (traveledPolyline) {
        travelDostMap.removeLayer(traveledPolyline);
        traveledPolyline = null;
    }
    if (remainingPolyline) {
        travelDostMap.removeLayer(remainingPolyline);
        remainingPolyline = null;
    }

    const bounds = [];

    // Extract ordered stop coordinates
    const stopCoords = (routeStops && routeStops.length > 0)
        ? routeStops.map(s => [parseFloat(s.lat || s.latitude), parseFloat(s.lng || s.longitude || s.lon)]).filter(p => !isNaN(p[0]) && !isNaN(p[1]))
        : [];

    const sourcePoint = stopCoords.length > 0 ? stopCoords[0] : null;
    const destPoint = stopCoords.length > 0 ? stopCoords[stopCoords.length - 1] : null;
    currentSourceStopCoords = sourcePoint;
    currentDestStopCoords = destPoint;

    const sourceStopName = (routeStops && routeStops[0]) ? (routeStops[0].name || routeStops[0].stop_name || 'Origin') : 'Origin';
    const destStopName = (routeStops && routeStops.length > 0) ? (routeStops[routeStops.length - 1].name || routeStops[routeStops.length - 1].stop_name || 'Terminus') : 'Terminus';

    // 1. FULL CORRIDOR: From Source to Destination (ONE TYPE: Solid Electric Blue)
    const fullRoutePoints = (roadGeometry && roadGeometry.length >= 2)
        ? roadGeometry
        : stopCoords;

    if (fullRoutePoints && fullRoutePoints.length >= 2) {
        sourceToDestPolyline = L.polyline(fullRoutePoints, {
            color: '#2563eb',
            weight: 6,
            opacity: 0.92,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(travelDostMap);

        sourceToDestPolyline.bindTooltip(`🛣️ Route: ${sourceStopName} ➔ ${destStopName} (${routeStops.length} stops)`, {
            sticky: true,
            className: 'custom-transit-tooltip'
        });

        fullRoutePoints.forEach(p => bounds.push(p));
    }

    // Resolve bus location coordinates
    let activeBusPt = null;
    if (busLatLng && !isNaN(busLatLng[0]) && !isNaN(busLatLng[1])) {
        activeBusPt = [busLatLng[0], busLatLng[1]];
    } else if (sourcePoint) {
        activeBusPt = sourcePoint;
    }

    // 2. BUS LOCATION TO SOURCE: (DIFFERENT TYPE: Dashed Amber #f59e0b)
    if (activeBusPt && sourcePoint) {
        busToSourcePolyline = L.polyline([activeBusPt, sourcePoint], {
            color: '#f59e0b',
            weight: 4.5,
            opacity: 0.95,
            dashArray: '8, 10',
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(travelDostMap);

        const distKm = calculateHaversineDistanceKm(activeBusPt[0], activeBusPt[1], sourcePoint[0], sourcePoint[1]);
        const distStr = distKm < 0.05 ? 'At Boarding Stop' : (distKm < 1.0 ? `${Math.round(distKm * 1000)} m away` : `${distKm.toFixed(1)} km away`);

        busToSourcePolyline.bindTooltip(`🚌 Bus Location ➔ Source Stop (${sourceStopName}): ${distStr}`, {
            sticky: true,
            className: 'custom-transit-tooltip'
        });

        bounds.push(activeBusPt);
        bounds.push(sourcePoint);
    }

    // Plot Route Stop Markers
    if (routeStops && routeStops.length > 0) {
        plotDetailedRouteStops(routeStops, activeBusPt);
    }

    if (bounds.length > 0) {
        travelDostMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }

    setTimeout(() => { if (travelDostMap) travelDostMap.invalidateSize(true); }, 100);
    setTimeout(() => { if (travelDostMap) travelDostMap.invalidateSize(true); }, 300);
}

// Backward compatibility alias
function renderTraveledAndRemainingRoute(busLatLng, routeStops, traveledRoadPoints, remainingRoadPoints, breadcrumbsPoints, roadGeometry) {
    renderTrackingPolylines(busLatLng, routeStops, roadGeometry || remainingRoadPoints, traveledRoadPoints, remainingRoadPoints, breadcrumbsPoints);
}

/**
 * Dynamically appends a coordinate to the active traveled breadcrumbs polyline in real-time
 */
function appendTraveledCoordinate(lat, lng) {
    if (!travelDostMap || isNaN(lat) || isNaN(lng)) return;
    const newPoint = L.latLng(lat, lng);
    if (traveledPolyline) {
        const pts = traveledPolyline.getLatLngs();
        if (pts.length === 0 || pts[pts.length - 1].distanceTo(newPoint) > 1.0) {
            traveledPolyline.addLatLng(newPoint);
        }
    } else {
        traveledPolyline = L.polyline([newPoint], {
            color: '#10b981',
            weight: 6,
            opacity: 0.95,
            lineJoin: 'round',
            lineCap: 'round'
        }).addTo(travelDostMap);
    }

    // Update remaining path starting point if active
    if (remainingPolyline) {
        const remainingPts = remainingPolyline.getLatLngs();
        if (remainingPts.length > 0) {
            remainingPts[0] = newPoint;
            remainingPolyline.setLatLngs(remainingPts);
        }
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

/**
 * Plot bus stops for Nearby Stops Locator with walking distance badges
 */
function plotBusStops(stopsArray) {
    if (!travelDostMap || !busStopMarkersGroup || !stopsArray) return;
    busStopMarkersGroup.clearLayers();

    const bounds = [];
    if (passengerMarker) {
        bounds.push(passengerMarker.getLatLng());
    }

    stopsArray.forEach((stop, idx) => {
        const lat = parseFloat(stop.latitude || stop.lat);
        const lng = parseFloat(stop.longitude || stop.lng);
        if (isNaN(lat) || isNaN(lng)) return;

        bounds.push([lat, lng]);

        const distLabel = stop.distance_km 
            ? (stop.distance_km < 1.0 ? `${stop.distance_meters || Math.round(stop.distance_km * 1000)} m` : `${Number(stop.distance_km).toFixed(1)} km`)
            : '';

        const stopIcon = L.divIcon({
            className: 'custom-stop-div-icon',
            html: `
                <div class="stop-marker-icon" style="background: #ffffff; color: #1e293b; border-color: #ef4444; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; border: 2px solid #ef4444; font-weight: 700; font-size: 0.75rem; white-space: nowrap;">
                    <span style="background: #ef4444; color: white; border-radius: 50%; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.65rem;">${idx + 1}</span>
                    <span>${stop.name || stop.stop_name}</span>
                    ${distLabel ? `<span style="background: #f1f5f9; color: #64748b; font-size: 0.65rem; padding: 1px 6px; border-radius: 4px;">${distLabel}</span>` : ''}
                </div>
            `,
            iconSize: [180, 30],
            iconAnchor: [90, 15]
        });

        const marker = L.marker([lat, lng], { icon: stopIcon });
        marker.bindPopup(`
            <div class="p-2" style="min-width: 200px;">
                <div class="d-flex align-items-center gap-2 mb-1">
                    <span class="badge bg-danger rounded-pill">Stop #${idx + 1}</span>
                    ${distLabel ? `<span class="badge bg-light text-secondary border">${distLabel} away</span>` : ''}
                </div>
                <strong class="d-block text-dark fs-6 mb-1">${stop.name || stop.stop_name}</strong>
                <p class="small text-secondary m-0 mb-2">${stop.area || 'Hubballi–Dharwad Twin Cities'}</p>
                <a href="/find-route/?source=${stop.id || ''}" class="btn btn-sm btn-outline-primary rounded-pill px-3 w-100 fw-semibold" style="font-size: 0.78rem;">
                    Plan Bus from Here ➔
                </a>
            </div>
        `);
        busStopMarkersGroup.addLayer(marker);
    });

    if (bounds.length > 0) {
        travelDostMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
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
 * Real-Time Bus Marker Plotter (Always Renders & Tracks Bus Position)
 */
function updateBusMarkerOnMap(busData) {
    if (!travelDostMap || !busData) return;

    const busId = busData.bus_id || busData.id;
    const lat = parseFloat(busData.latitude);
    const lng = parseFloat(busData.longitude);
    const status = busData.status || busData.tracking_status || 'LIVE';
    const tripStatus = (busData.trip_status || '').toUpperCase();
    const busNum = busData.bus_number || '';

    // Only skip if coordinates are completely invalid
    if (isNaN(lat) || isNaN(lng)) {
        return;
    }

    const isLive = status === 'LIVE' && (!tripStatus || ['ACTIVE', 'IN_PROGRESS', 'IN_TRANSIT'].includes(tripStatus));
    const speedStr = busData.speed !== undefined && busData.speed !== null ? Number(busData.speed).toFixed(1) : (isLive ? '30.0' : '0.0');

    const popupContent = `
        <div class="p-2" style="min-width: 210px;">
            <div class="d-flex align-items-center justify-content-between gap-2 mb-2">
                <strong class="text-primary fs-6"><i class="fa-solid fa-bus me-1"></i> Bus ${busNum}</strong>
                <span class="badge ${isLive ? 'bg-success' : 'bg-secondary'}">${isLive ? '<span class="live-dot me-1"></span> LIVE' : 'SCHEDULED'}</span>
            </div>
            <p class="m-0 small"><strong>Route:</strong> ${busData.route_name || 'NWKRTC Service'}</p>
            <p class="m-0 small"><strong>Speed:</strong> ${speedStr} km/h</p>
            <p class="m-0 small text-muted"><strong>Status:</strong> ${isLive ? 'Real-Time GPS (3s sync)' : 'Scheduled / Terminal Standby'}</p>
        </div>
    `;

    if (busMarkersMap[busId]) {
        busMarkersMap[busId].setLatLng([lat, lng]);
        busMarkersMap[busId].setIcon(createBusIcon(isLive ? 'LIVE' : 'SCHEDULED', busNum, busData.heading || 0));
        if (busMarkersMap[busId].getPopup()) {
            busMarkersMap[busId].getPopup().setContent(popupContent);
        }
    } else {
        const marker = L.marker([lat, lng], { icon: createBusIcon(isLive ? 'LIVE' : 'SCHEDULED', busNum, busData.heading || 0) }).addTo(travelDostMap);
        marker.bindPopup(popupContent);
        busMarkersMap[busId] = marker;
    }

    // Dynamically update the Bus Location to Source Stop polyline (Different Type: Dashed Amber)
    if (busToSourcePolyline && currentSourceStopCoords) {
        busToSourcePolyline.setLatLngs([[lat, lng], currentSourceStopCoords]);
    } else if (currentSourceStopCoords && travelDostMap) {
        busToSourcePolyline = L.polyline([[lat, lng], currentSourceStopCoords], {
            color: '#f59e0b',
            weight: 4.5,
            opacity: 0.95,
            dashArray: '8, 10',
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(travelDostMap);
    }

    // Dynamically append to traveled breadcrumbs polyline
    appendTraveledCoordinate(lat, lng);
}
