/**
 * Travel Dost — Trip Lifecycle & Proximity Announcer Engine
 * 
 * Implements context-aware trip lifecycle management:
 * 1. Pre-Boarding Proximity (100-150m, 30-50m, <20m near zero speed)
 * 2. Automatic Trip Start (Driver & Passenger GPS sync <= 30m, speed > 10 km/h)
 * 3. En-Route & Dynamic Stop Progression (Departing stops -> "Next stop is: [Name]")
 * 4. Relative Destination Countdown (3 stops, 2 stops, 1 stop away)
 * 5. Destination Arrival (< 20m) & Deboarding Announcement
 * 6. Pluggable Web Speech API Audio Synthesis & Visual Notifications
 * 7. Anti-Spam Hysteresis Buffers for GPS Jitter Elimination
 */

(function(window) {
    'use strict';

    // Formal State Machine
    const TripState = {
        WAITING_FOR_BUS: 'WAITING_FOR_BUS',
        PRE_BOARDING_COUNTDOWN: 'PRE_BOARDING_COUNTDOWN',
        BUS_ARRIVING: 'BUS_ARRIVING',
        BOARDED_TRIP_ACTIVE: 'BOARDED_TRIP_ACTIVE',
        BOARDED_IN_TRANSIT: 'BOARDED_IN_TRANSIT',
        APPROACHING_DESTINATION: 'APPROACHING_DESTINATION',
        ARRIVED_DESTINATION: 'ARRIVED_DESTINATION',
        COMPLETED: 'COMPLETED'
    };

    /**
     * Haversine distance formula returning distance in meters between two lat/lng coordinates.
     */
    function haversineMeters(lat1, lon1, lat2, lon2) {
        const R = 6371000; // Mean Earth radius in meters
        const toRad = Math.PI / 180;
        const dLat = (lat2 - lat1) * toRad;
        const dLon = (lon2 - lon1) * toRad;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    class TripLifecycleAnnouncer {
        constructor(config = {}) {
            this.routeStops = config.routeStops || [];
            this.pickupStopId = config.pickupStopId || null;
            this.destinationStopId = config.destinationStopId || null;
            this.busNumber = config.busNumber || '42';
            this.isMuted = config.isMuted !== undefined ? config.isMuted : false;
            this.speechRate = config.speechRate || 0.95;
            this.speechPitch = config.speechPitch || 1.0;

            // Thresholds (Meters & km/h)
            this.THRESHOLDS = {
                PRE_APPROACH_MIN: 50.0,
                PRE_APPROACH_MAX: 100.0,
                PRE_IMMINENT_MIN: 30.0,
                PRE_IMMINENT_MAX: 50.0,
                PRE_ARRIVED_DIST: 20.0,
                PRE_MAX_STOP_SPEED: 6.0,   // km/h (near zero speed)

                BOARDING_SYNC_RADIUS: 25.0, // meters between passenger and driver (merged)
                BOARDING_MIN_SPEED: 10.0,   // km/h moving away from pickup

                INTERMEDIATE_APPROACH: 100.0,
                INTERMEDIATE_CLEAR: 25.0,
                DESTINATION_ARRIVAL: 20.0,

                HYSTERESIS_BUFFER: 5.0      // meters to prevent jitter oscillation
            };

            this.state = TripState.WAITING_FOR_BUS;

            this.driverGps = null;
            this.passengerGps = null;

            this.pickupStop = null;
            this.destinationStop = null;
            this.pickupIndex = -1;
            this.destinationIndex = -1;
            this.currentStopIndex = -1;
            this.nextStopIndex = -1;

            // Anti-spam registry
            this.triggeredEvents = new Set();
            this.visitedStopIds = new Set();
            this.announcementHistory = [];
            this.listeners = {};

            // Audio speech synthesis setup
            this.speechSynth = window.speechSynthesis || null;
            this.preferredVoice = null;
            this._initVoice();

            if (this.routeStops.length > 0 && this.pickupStopId && this.destinationStopId) {
                this.initializeTrip(this.routeStops, this.pickupStopId, this.destinationStopId);
            }
        }

        _initVoice() {
            if (!this.speechSynth) return;
            const setVoice = () => {
                const voices = this.speechSynth.getVoices();
                // Prefer clean English voice (e.g. Google UK English, Natural, Samantha)
                this.preferredVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha'))) ||
                                     voices.find(v => v.lang.startsWith('en')) ||
                                     voices[0] || null;
            };
            setVoice();
            if (speechSynthesis.onvoiceschanged !== undefined) {
                speechSynthesis.onvoiceschanged = setVoice;
            }
        }

        initializeTrip(routeStops, pickupStopId, destinationStopId) {
            this.routeStops = Array.isArray(routeStops) ? [...routeStops] : [];
            this.pickupStopId = pickupStopId;
            this.destinationStopId = destinationStopId;

            this.pickupIndex = this.routeStops.findIndex(st => String(st.id) === String(pickupStopId) || String(st.stop_id) === String(pickupStopId));
            this.destinationIndex = this.routeStops.findIndex(st => String(st.id) === String(destinationStopId) || String(st.stop_id) === String(destinationStopId));

            if (this.pickupIndex === -1) {
                console.warn('[TripAnnouncer] Pickup stop not found in route stops.');
                return false;
            }
            if (this.destinationIndex === -1) {
                console.warn('[TripAnnouncer] Destination stop not found in route stops.');
                return false;
            }
            if (this.pickupIndex >= this.destinationIndex) {
                console.warn('[TripAnnouncer] Pickup stop must precede destination stop.');
                return false;
            }

            this.pickupStop = this.routeStops[this.pickupIndex];
            this.destinationStop = this.routeStops[this.destinationIndex];

            this.currentStopIndex = this.pickupIndex;
            this.nextStopIndex = this.pickupIndex + 1;
            this.state = TripState.WAITING_FOR_BUS;

            this.triggeredEvents.clear();
            this.visitedStopIds.clear();
            this.announcementHistory = [];

            this.emit('initialized', {
                pickupStop: this.pickupStop,
                destinationStop: this.destinationStop,
                totalRouteStops: this.routeStops.length,
                stopsRemaining: this.destinationIndex - this.pickupIndex
            });

            return true;
        }

        // Event Emitter Support
        on(event, handler) {
            if (!this.listeners[event]) this.listeners[event] = [];
            this.listeners[event].push(handler);
            return this;
        }

        off(event, handler) {
            if (!this.listeners[event]) return this;
            this.listeners[event] = this.listeners[event].filter(h => h !== handler);
            return this;
        }

        emit(event, data) {
            if (this.listeners[event]) {
                this.listeners[event].forEach(handler => {
                    try { handler(data); } catch (err) { console.error(`[TripAnnouncer Error in ${event}]`, err); }
                });
            }
        }

        _transitionState(newState, meta = {}) {
            if (this.state === newState) return;
            const oldState = this.state;
            this.state = newState;
            const payload = {
                oldState,
                newState,
                timestamp: new Date().toISOString(),
                ...meta
            };
            this.emit('stateChange', payload);
        }

        triggerAnnouncement(eventId, message, type, meta = {}) {
            if (this.triggeredEvents.has(eventId)) return; // Strict anti-spam de-duplication

            this.triggeredEvents.add(eventId);

            const record = {
                id: eventId,
                message,
                type,
                state: this.state,
                timestamp: new Date().toISOString(),
                meta
            };
            this.announcementHistory.push(record);

            // 1. Play Voice Audio via Web Speech API
            this.speak(message);

            // 2. Render visual banner / toast notification
            this._showVisualNotification(message, type);

            // 3. Emit event to listeners
            this.emit('announcement', record);
        }

        speak(text) {
            if (this.isMuted || !this.speechSynth) return;

            try {
                // Resume in case audio context was suspended
                if (this.speechSynth.paused) {
                    this.speechSynth.resume();
                }

                // Cancel existing utterance to announce current high-priority message cleanly
                this.speechSynth.cancel();

                const utterance = new SpeechSynthesisUtterance(text);
                if (this.preferredVoice) utterance.voice = this.preferredVoice;
                utterance.rate = this.speechRate;
                utterance.pitch = this.speechPitch;
                utterance.volume = 1.0;

                this.speechSynth.speak(utterance);
            } catch (e) {
                console.warn('[TripAnnouncer Speech Error]', e);
            }
        }

        _showVisualNotification(message, type) {
            // Dispatches to on-page notification container or creates floating toast
            let container = document.getElementById('tripAnnouncerToastContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'tripAnnouncerToastContainer';
                container.style.cssText = `
                    position: fixed;
                    bottom: 24px;
                    right: 24px;
                    z-index: 99999;
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                    max-width: 380px;
                    pointer-events: none;
                `;
                document.body.appendChild(container);
            }

            const toast = document.createElement('div');
            toast.className = 'trip-announcer-toast';
            toast.style.cssText = `
                background: rgba(15, 23, 42, 0.95);
                backdrop-filter: blur(12px);
                color: #ffffff;
                padding: 14px 18px;
                border-radius: 16px;
                border-left: 5px solid #38bdf8;
                box-shadow: 0 16px 36px rgba(0,0,0,0.45);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                align-items: flex-start;
                gap: 12px;
                animation: toastSlideIn 0.3s ease forwards;
                pointer-events: auto;
            `;

            let iconHtml = '<i class="fa-solid fa-volume-high text-info" style="font-size: 1.2rem; margin-top: 2px;"></i>';
            if (type.includes('ARRIVED')) {
                toast.style.borderLeftColor = '#10b981';
                iconHtml = '<i class="fa-solid fa-circle-check text-success" style="font-size: 1.2rem; margin-top: 2px;"></i>';
            } else if (type.includes('IMMINENT') || type.includes('COUNTDOWN_1')) {
                toast.style.borderLeftColor = '#f59e0b';
                iconHtml = '<i class="fa-solid fa-triangle-exclamation text-warning" style="font-size: 1.2rem; margin-top: 2px;"></i>';
            } else if (type.includes('STARTED')) {
                toast.style.borderLeftColor = '#3b82f6';
                iconHtml = '<i class="fa-solid fa-bus text-primary" style="font-size: 1.2rem; margin-top: 2px;"></i>';
            }

            toast.innerHTML = `
                ${iconHtml}
                <div style="flex-grow: 1;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; font-weight: 700; margin-bottom: 2px;">
                        Trip Assistant
                    </div>
                    <div style="font-size: 0.9rem; line-height: 1.35; font-weight: 600;">
                        ${message}
                    </div>
                </div>
            `;

            container.appendChild(toast);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(10px)';
                toast.style.transition = 'all 0.4s ease';
                setTimeout(() => toast.remove(), 400);
            }, 6500);
        }

        // Ingest continuous Passenger GPS
        ingestPassengerGps(gpsUpdate) {
            if (!gpsUpdate || gpsUpdate.latitude === undefined || gpsUpdate.longitude === undefined) return;
            this.passengerGps = {
                latitude: parseFloat(gpsUpdate.latitude),
                longitude: parseFloat(gpsUpdate.longitude),
                speed: parseFloat(gpsUpdate.speed || 0.0),
                timestamp: gpsUpdate.timestamp || new Date().toISOString()
            };
        }

        // Ingest continuous Driver / Bus GPS (Trigger of state machine)
        ingestDriverGps(telemetry) {
            if (!telemetry || telemetry.latitude === undefined || telemetry.longitude === undefined) return;

            const lat = parseFloat(telemetry.latitude);
            const lon = parseFloat(telemetry.longitude);
            const speed = parseFloat(telemetry.speed || 0.0);
            const heading = parseFloat(telemetry.heading || 0.0);

            this.driverGps = {
                latitude: lat,
                longitude: lon,
                speed,
                heading,
                timestamp: telemetry.timestamp || new Date().toISOString()
            };

            if (this.state === TripState.COMPLETED || !this.pickupStop || !this.destinationStop) {
                return this.getSnapshot();
            }

            // ---------------------------------------------------------
            // 1. PRE-BOARDING & PROXIMITY DETECTION
            // ---------------------------------------------------------
            if (this.state === TripState.WAITING_FOR_BUS || this.state === TripState.PRE_BOARDING_COUNTDOWN || this.state === TripState.BUS_ARRIVING) {
                const pickupLat = parseFloat(this.pickupStop.lat);
                const pickupLng = parseFloat(this.pickupStop.lng || this.pickupStop.lon);
                const distToPickup = haversineMeters(lat, lon, pickupLat, pickupLng);

                // Upstream pre-boarding stop countdown (when bus is approaching prior stops)
                if (this.pickupIndex > 0) {
                    let closestPreIdx = -1;
                    let minPreDist = Infinity;
                    for (let i = 0; i < this.pickupIndex; i++) {
                        const st = this.routeStops[i];
                        const sLat = parseFloat(st.lat);
                        const sLng = parseFloat(st.lng || st.lon);
                        const d = haversineMeters(lat, lon, sLat, sLng);
                        if (d < minPreDist) {
                            minPreDist = d;
                            closestPreIdx = i;
                        }
                    }

                    if (closestPreIdx !== -1 && minPreDist <= 120.0) {
                        const stopsAway = this.pickupIndex - closestPreIdx;
                        if (stopsAway === 3) {
                            if (this.state !== TripState.PRE_BOARDING_COUNTDOWN) {
                                this._transitionState(TripState.PRE_BOARDING_COUNTDOWN, { stopsAway: 3 });
                            }
                            this.triggerAnnouncement(
                                'countdown_preboard_3',
                                'Bus is 3 stops away from your pickup point.',
                                'COUNTDOWN_PREBOARD_3',
                                { stopsAway: 3, currentStopIndex: closestPreIdx }
                            );
                        } else if (stopsAway === 2) {
                            if (this.state !== TripState.PRE_BOARDING_COUNTDOWN) {
                                this._transitionState(TripState.PRE_BOARDING_COUNTDOWN, { stopsAway: 2 });
                            }
                            this.triggerAnnouncement(
                                'countdown_preboard_2',
                                'Bus is 2 stops away.',
                                'COUNTDOWN_PREBOARD_2',
                                { stopsAway: 2, currentStopIndex: closestPreIdx }
                            );
                        } else if (stopsAway === 1) {
                            if (this.state !== TripState.PRE_BOARDING_COUNTDOWN) {
                                this._transitionState(TripState.PRE_BOARDING_COUNTDOWN, { stopsAway: 1 });
                            }
                            this.triggerAnnouncement(
                                'countdown_preboard_1',
                                'Bus is at the previous stop. Arriving next at your location.',
                                'COUNTDOWN_PREBOARD_1',
                                { stopsAway: 1, currentStopIndex: closestPreIdx }
                            );
                        }
                    }
                }

                // Approaching Alert (50m - 100m)
                if (distToPickup <= (100.0 + this.THRESHOLDS.HYSTERESIS_BUFFER) &&
                    distToPickup >= (50.0 - this.THRESHOLDS.HYSTERESIS_BUFFER)) {
                    if (this.state !== TripState.BUS_ARRIVING) {
                        this._transitionState(TripState.BUS_ARRIVING, { distanceToPickup: distToPickup });
                    }
                    this.triggerAnnouncement(
                        'preboarding_approaching',
                        'Bus is approaching your stop (within 100 meters).',
                        'PRE_BOARDING_APPROACHING',
                        { distanceMeters: Math.round(distToPickup), stopName: this.pickupStop.name }
                    );
                }

                // Arriving / Imminent Alert (30m - 50m)
                if (distToPickup <= (this.THRESHOLDS.PRE_IMMINENT_MAX + this.THRESHOLDS.HYSTERESIS_BUFFER) &&
                    distToPickup >= (this.THRESHOLDS.PRE_IMMINENT_MIN - this.THRESHOLDS.HYSTERESIS_BUFFER)) {
                    if (this.state !== TripState.BUS_ARRIVING) {
                        this._transitionState(TripState.BUS_ARRIVING, { distanceToPickup: distToPickup });
                    }
                    this.triggerAnnouncement(
                        'preboarding_imminent',
                        'The bus is within 50 meters of your stop. Please be ready.',
                        'PRE_BOARDING_IMMINENT',
                        { distanceMeters: Math.round(distToPickup), stopName: this.pickupStop.name }
                    );
                }

                // Arrived / Boarding Alert (< 20m and speed near zero)
                if (distToPickup <= this.THRESHOLDS.PRE_ARRIVED_DIST && speed <= this.THRESHOLDS.PRE_MAX_STOP_SPEED) {
                    this.triggerAnnouncement(
                        'preboarding_arrived',
                        `Bus #${this.busNumber} has arrived! Please board now.`,
                        'PRE_BOARDING_ARRIVED',
                        { distanceMeters: Math.round(distToPickup), speed, busNumber: this.busNumber }
                    );
                }

                // -----------------------------------------------------
                // 2. AUTOMATIC TRIP START (Driver & Passenger Sync)
                // -----------------------------------------------------
                // If passenger GPS is available, verify passenger and driver within 25m
                const pLat = this.passengerGps ? this.passengerGps.latitude : pickupLat;
                const pLon = this.passengerGps ? this.passengerGps.longitude : pickupLng;

                const passDriverDist = haversineMeters(lat, lon, pLat, pLon);
                const distAwayFromPickup = haversineMeters(lat, lon, pickupLat, pickupLng);

                // Both within 25m AND bus begins moving (speed > 10 km/h away from pickup point)
                if (passDriverDist <= this.THRESHOLDS.BOARDING_SYNC_RADIUS &&
                    speed >= this.THRESHOLDS.BOARDING_MIN_SPEED &&
                    distAwayFromPickup >= 20.0) {
                    
                    const destName = this.destinationStop.name;
                    this._transitionState(TripState.BOARDED_TRIP_ACTIVE, {
                        syncDistance: passDriverDist,
                        speed,
                        distAwayFromPickup
                    });

                    this.triggerAnnouncement(
                        'trip_started',
                        `Trip started. Welcome aboard! You are now aboard Bus #${this.busNumber}. Enjoy your trip!`,
                        'TRIP_STARTED',
                        { destinationName: destName, speed, busNumber: this.busNumber }
                    );

                    this.emit('passengerBoarded', {
                        busNumber: this.busNumber,
                        passengerGps: this.passengerGps,
                        driverGps: this.driverGps,
                        speed: speed
                    });

                    this.visitedStopIds.add(String(this.pickupStop.id || this.pickupIndex));
                    this._announceDepartureToNextStop();
                }
            }

            // ---------------------------------------------------------
            // 3. EN-ROUTE DYNAMIC STOP PROGRESSION & COUNTDOWN
            // ---------------------------------------------------------
            else if (this.state === TripState.BOARDED_TRIP_ACTIVE || this.state === TripState.BOARDED_IN_TRANSIT || this.state === TripState.APPROACHING_DESTINATION) {
                this._evaluateEnRouteProgression(lat, lon, speed);
            }


            return this.getSnapshot();
        }

        _evaluateEnRouteProgression(lat, lon, speed) {
            const destLat = parseFloat(this.destinationStop.lat);
            const destLng = parseFloat(this.destinationStop.lng || this.destinationStop.lon);
            const distToFinalDest = haversineMeters(lat, lon, destLat, destLng);

            // ---------------------------------------------------------
            // 5. DESTINATION ARRIVAL (< 20m)
            // ---------------------------------------------------------
            if (distToFinalDest <= this.THRESHOLDS.DESTINATION_ARRIVAL) {
                const destName = this.destinationStop.name;
                this._transitionState(TripState.ARRIVED_DESTINATION, { distanceToDest: distToFinalDest });

                this.triggerAnnouncement(
                    'destination_arrived',
                    `You have arrived at your destination: ${destName}. Please safely exit the bus.`,
                    'DESTINATION_ARRIVED',
                    { destinationName: destName, distanceMeters: Math.round(distToFinalDest) }
                );

                this._transitionState(TripState.COMPLETED);
                this.emit('tripComplete', {
                    destination: destName,
                    completedAt: new Date().toISOString()
                });
                return;
            }

            // Intermediate stop tracking
            if (this.nextStopIndex < this.routeStops.length) {
                const targetStop = this.routeStops[this.nextStopIndex];
                const tLat = parseFloat(targetStop.lat);
                const tLng = parseFloat(targetStop.lng || targetStop.lon);
                const distToTarget = haversineMeters(lat, lon, tLat, tLng);

                const targetId = String(targetStop.id || this.nextStopIndex);
                const approachKey = `approaching_stop_${targetId}`;

                // Approaching intermediate stop within 100m
                if (distToTarget <= this.THRESHOLDS.INTERMEDIATE_APPROACH) {
                    if (!this.visitedStopIds.has(targetId)) {
                        this.triggerAnnouncement(
                            approachKey,
                            `Approaching stop: ${targetStop.name}.`,
                            'STOP_APPROACHING',
                            { stopName: targetStop.name, distanceMeters: Math.round(distToTarget) }
                        );
                    }
                }

                // Cleared stop geofence
                if (distToTarget <= this.THRESHOLDS.INTERMEDIATE_CLEAR ||
                   (this.triggeredEvents.has(approachKey) && distToTarget > this.THRESHOLDS.INTERMEDIATE_CLEAR && speed > 10.0)) {
                    
                    if (!this.visitedStopIds.has(targetId)) {
                        this.visitedStopIds.add(targetId);
                        this.currentStopIndex = this.nextStopIndex;
                        this.nextStopIndex++;

                        this.emit('stopProgress', {
                            currentStop: targetStop,
                            nextStopIndex: this.nextStopIndex,
                            stopsRemaining: this.destinationIndex - this.currentStopIndex
                        });

                        // Announce next stop upon departure
                        this._announceDepartureToNextStop();
                        // Check relative destination countdown
                        this._checkDestinationCountdown();
                    }
                }
            }
        }

        _announceDepartureToNextStop() {
            if (this.nextStopIndex < this.routeStops.length) {
                const nextStop = this.routeStops[this.nextStopIndex];
                const nextId = String(nextStop.id || this.nextStopIndex);
                this.triggerAnnouncement(
                    `departed_for_stop_${nextId}`,
                    `Next stop is: ${nextStop.name}.`,
                    'NEXT_STOP_ANNOUNCEMENT',
                    { nextStopName: nextStop.name, nextStopIndex: this.nextStopIndex }
                );
            }
        }

        _checkDestinationCountdown() {
            const stopsRemaining = this.destinationIndex - this.currentStopIndex;
            const destName = this.destinationStop.name;

            if (stopsRemaining === 3) {
                if (this.state === TripState.BOARDED_TRIP_ACTIVE) {
                    this._transitionState(TripState.APPROACHING_DESTINATION, { stopsRemaining: 3 });
                }
                this.triggerAnnouncement(
                    'countdown_3_stops',
                    `Notice: Your destination ${destName} is approaching in 3 stops.`,
                    'COUNTDOWN_3_STOPS',
                    { stopsRemaining: 3, destinationName: destName }
                );
            } else if (stopsRemaining === 2) {
                if (this.state === TripState.BOARDED_TRIP_ACTIVE) {
                    this._transitionState(TripState.APPROACHING_DESTINATION, { stopsRemaining: 2 });
                }
                this.triggerAnnouncement(
                    'countdown_2_stops',
                    `Your destination is approaching after the next stop (2 stops away).`,
                    'COUNTDOWN_2_STOPS',
                    { stopsRemaining: 2, destinationName: destName }
                );
            } else if (stopsRemaining === 1) {
                if (this.state === TripState.BOARDED_TRIP_ACTIVE || this.state === TripState.APPROACHING_DESTINATION) {
                    this._transitionState(TripState.APPROACHING_DESTINATION, { stopsRemaining: 1 });
                }
                this.triggerAnnouncement(
                    'countdown_1_stop',
                    `Next stop is your destination: ${destName}. Please prepare your belongings.`,
                    'COUNTDOWN_1_STOP',
                    { stopsRemaining: 1, destinationName: destName }
                );
            }
        }

        toggleMute() {
            this.isMuted = !this.isMuted;
            if (this.isMuted && this.speechSynth) {
                this.speechSynth.cancel();
            }
            this.emit('muteToggled', { isMuted: this.isMuted });
            return this.isMuted;
        }

        setMuted(muted) {
            this.isMuted = !!muted;
            if (this.isMuted && this.speechSynth) {
                this.speechSynth.cancel();
            }
            this.emit('muteToggled', { isMuted: this.isMuted });
        }

        getSnapshot() {
            let distToPickup = null;
            let distToDest = null;
            let distToNext = null;

            if (this.driverGps && this.pickupStop && this.destinationStop) {
                distToPickup = Math.round(haversineMeters(
                    this.driverGps.latitude, this.driverGps.longitude,
                    parseFloat(this.pickupStop.lat), parseFloat(this.pickupStop.lng || this.pickupStop.lon)
                ));
                distToDest = Math.round(haversineMeters(
                    this.driverGps.latitude, this.driverGps.longitude,
                    parseFloat(this.destinationStop.lat), parseFloat(this.destinationStop.lng || this.destinationStop.lon)
                ));

                if (this.nextStopIndex < this.routeStops.length) {
                    const nStop = this.routeStops[this.nextStopIndex];
                    distToNext = Math.round(haversineMeters(
                        this.driverGps.latitude, this.driverGps.longitude,
                        parseFloat(nStop.lat), parseFloat(nStop.lng || nStop.lon)
                    ));
                }
            }

            const currentStopObj = (this.currentStopIndex >= 0 && this.currentStopIndex < this.routeStops.length)
                ? this.routeStops[this.currentStopIndex] : null;
            const nextStopObj = (this.nextStopIndex >= 0 && this.nextStopIndex < this.routeStops.length)
                ? this.routeStops[this.nextStopIndex] : null;

            return {
                state: this.state,
                isMuted: this.isMuted,
                pickupStop: this.pickupStop ? this.pickupStop.name : null,
                destinationStop: this.destinationStop ? this.destinationStop.name : null,
                currentStop: currentStopObj ? currentStopObj.name : null,
                nextStop: nextStopObj ? nextStopObj.name : null,
                nextStopIndex: this.nextStopIndex,
                stopsRemaining: (this.destinationIndex >= 0 && this.currentStopIndex >= 0) ? Math.max(0, this.destinationIndex - this.currentStopIndex) : 0,
                distanceToPickupMeters: distToPickup,
                distanceToDestinationMeters: distToDest,
                distanceToNextStopMeters: distToNext,
                driverGps: this.driverGps,
                passengerGps: this.passengerGps,
                announcementsCount: this.announcementHistory.length,
                latestAnnouncement: this.announcementHistory.length > 0 ? this.announcementHistory[this.announcementHistory.length - 1] : null,
                isCompleted: this.state === TripState.COMPLETED
            };
        }

        reset() {
            if (this.speechSynth) this.speechSynth.cancel();
            this.state = TripState.WAITING_FOR_BUS;
            this.driverGps = null;
            this.triggeredEvents.clear();
            this.visitedStopIds.clear();
            this.announcementHistory = [];
            this.emit('reset', {});
        }

        /**
         * Slices full road network polyline coordinates into traveled vs remaining based on current bus location.
         * Completed portion (traveled): faded/muted gray where bus already drove.
         * Remaining portion: vibrant upcoming path ahead of the bus marker.
         * @param {Array<[number, number]>} roadCoords - Array of [lat, lon] coordinates.
         * @param {number} busLat - Current bus latitude.
         * @param {number} busLon - Current bus longitude.
         * @returns {{ traveled: Array<[number, number]>, remaining: Array<[number, number]>, closestIndex: number, distanceMeters: number }}
         */
        static slicePolyline(roadCoords, busLat, busLon) {
            if (!roadCoords || roadCoords.length === 0) {
                return { traveled: [], remaining: [], closestIndex: -1, distanceMeters: 0 };
            }
            if (roadCoords.length === 1) {
                return { traveled: [[busLat, busLon]], remaining: [roadCoords[0]], closestIndex: 0, distanceMeters: 0 };
            }

            let minDistance = Infinity;
            let closestIndex = 0;

            for (let i = 0; i < roadCoords.length; i++) {
                const pt = roadCoords[i];
                const d = haversineMeters(busLat, busLon, pt[0], pt[1]);
                if (d < minDistance) {
                    minDistance = d;
                    closestIndex = i;
                }
            }

            // Sliced traveled portion: up to closest vertex, plus current bus position
            const traveled = roadCoords.slice(0, closestIndex + 1);
            traveled.push([busLat, busLon]);

            // Sliced remaining portion: begins from current bus position, followed by remaining road coordinates
            const remaining = [[busLat, busLon], ...roadCoords.slice(closestIndex + 1)];

            return {
                traveled,
                remaining,
                closestIndex,
                distanceMeters: Math.round(minDistance)
            };
        }

        /**
         * Asynchronously fetches road-following geometry adhering strictly to street networks via OSRM/backend.
         * Stops straight-line paths from cutting through houses and buildings.
         * @param {Array<{lat: number, lon: number}>} stops
         * @returns {Promise<Array<[number, number]>>}
         */
        static async fetchRoadSnappedRoute(stops) {
            if (!stops || stops.length < 2) {
                return stops ? stops.map(s => [s.lat, s.lon !== undefined ? s.lon : s.lng]) : [];
            }
            const latLons = stops.map(s => [s.lat, s.lon !== undefined ? s.lon : s.lng]);

            try {
                // Try backend cached road-geometry endpoint
                const resp = await fetch('/api/routes/road-geometry/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ coordinates: latLons })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.status === 'success' && data.geometry && data.geometry.coordinates && data.geometry.coordinates.length >= 2) {
                        return data.geometry.coordinates;
                    }
                }
            } catch (e) {
                console.debug('Backend road geometry fallback:', e);
            }

            // Fallback direct to OSRM driving profile
            try {
                const coordStr = stops.map(s => `${(s.lon !== undefined ? s.lon : s.lng).toFixed(6)},${s.lat.toFixed(6)}`).join(';');
                const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${coordStr}?overview=full&geometries=geojson`;
                const oResp = await fetch(osrmUrl);
                if (oResp.ok) {
                    const oData = await oResp.json();
                    if (oData.code === 'Ok' && oData.routes && oData.routes[0]) {
                        return oData.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
                    }
                }
            } catch (err) {
                console.debug('OSRM direct fallback error:', err);
            }

            return latLons;
        }
    }


    // Attach to global window
    window.TripState = TripState;
    window.TripLifecycleAnnouncer = TripLifecycleAnnouncer;

})(window);
