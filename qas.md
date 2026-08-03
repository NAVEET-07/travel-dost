# TRAVEL DOST — Comprehensive Major Project Viva Questions & Answers (qas)

This document (`qas.md`) contains an exhaustive, technical question-and-answer bank covering every single component of the **Travel Dost** project.

---

## 📑 SECTION I: COMPREHENSIVE QUESTION INDEX (QUESTIONS ONLY)

---

### PART 1: FRONTEND & UI/UX (HTML5, CSS3, JavaScript, jQuery, Leaflet.js, Bootstrap 5)

1. **Q1.1**: What frontend technologies and libraries are used in Travel Dost, and why were they chosen over frameworks like React or Angular?
2. **Q1.2**: How does Leaflet.js render interactive maps on the client side, and how is it configured in Travel Dost?
3. **Q1.3**: How are live bus markers dynamically moved on the Leaflet map without reloading or re-initializing the entire map object?
4. **Q1.4**: How does `driver_gps.js` capture the mobile phone's GPS coordinates using the HTML5 Geolocation API (`navigator.geolocation`)?
5. **Q1.5**: What is the difference between `getCurrentPosition()` and `watchPosition()` in the HTML5 Geolocation API?
6. **Q1.6**: How is the Viva Indoor Simulation Mode implemented in JavaScript when outdoor GPS signals are unavailable?
7. **Q1.7**: How does jQuery handle AJAX requests for resting API endpoints like `/api/buses/` and `/api/routes/<id>/add-stop/`?
8. **Q1.8**: How does `base.html` use Django Template Language (DTL) tags to render conditional navigation links based on user roles?
9. **Q1.9**: What CSS techniques are used for the dark glassmorphism and modern UI aesthetics in Travel Dost?
10. **Q1.10**: How does the Admin Dashboard handle dynamic stop creation on the frontend without refreshing the page?

---

### PART 2: BACKEND & WEBSOCKETS (Python, Django, Django REST Framework, Django Channels, Algorithms)

11. **Q2.1**: What is the overall backend architecture of Travel Dost, and what role does Django play in it?
12. **Q2.2**: What is the difference between WSGI and ASGI in Python web development, and why does Travel Dost use Daphne/ASGI?
13. **Q2.3**: What is Django Channels, and how does it handle WebSockets alongside standard HTTP requests?
14. **Q2.4**: How does `BusTrackingConsumer` in `tracking/consumers.py` manage WebSocket connections, message reception, and broadcasting?
15. **Q2.5**: How do Channel Layer Groups work in Django Channels for routing telemetry to specific bus subscribers (`bus_<id>`) and overview subscribers (`bus_all`)?
16. **Q2.6**: How is the Haversine Distance Formula implemented in Python to calculate the distance between geographic GPS coordinates?
17. **Q2.7**: How does the Intelligent Route Finder algorithm (`tracking/services/route_finder.py`) detect direct and 1-transfer connecting routes?
18. **Q2.8**: What Django REST Framework (DRF) components (ViewSets, APIViews, Serializers) are used in Travel Dost?
19. **Q2.9**: How does `BusLocationAPIView` handle fallback location updates when WebSocket connections are unavailable?
20. **Q2.10**: How does `database_sync_to_async` work when saving WebSocket telemetry to the SQLite database in asynchronous consumer functions?

---

### PART 3: DATABASE, MIGRATIONS & SECURITY / RBAC (SQLite, Models, Decorators, Sessions)

21. **Q3.1**: What database engine is used in Travel Dost, and how is the database schema structured?
22. **Q3.2**: How is the custom `User` model implemented by extending Django's `AbstractUser`?
23. **Q3.3**: How are user roles (`ADMIN`, `DRIVER`, `USER`) defined and validated in the `User` model?
24. **Q3.4**: How is the relationship between `Bus`, `Route`, `BusStop`, and `RouteStop` defined using Django ForeignKey fields?
25. **Q3.5**: How is the `driver` ForeignKey added to the `Bus` model to enforce that a driver sees ONLY their assigned bus?
26. **Q3.6**: What are Django Migrations, and what is the difference between `makemigrations` and `migrate`?
27. **Q3.7**: How do custom Python decorators (`@admin_required`, `@driver_required`, `@user_required`) enforce Role-Based Access Control (RBAC)?
28. **Q3.8**: What happens when an unauthenticated user or user with the wrong role attempts to access `/admin/dashboard/` or `/driver/dashboard/` directly via URL?
29. **Q3.9**: How does Django session-based authentication (`sessionid` cookie) work, and how does `/logout/` flush active sessions?
30. **Q3.10**: What is CSRF (Cross-Site Request Forgery), and how is CSRF protection handled in Django forms and AJAX requests?

---

### PART 4: SYSTEM ARCHITECTURE, IOT GPS TELEMETRY & VIVA DEMO WORKFLOW

31. **Q4.1**: How does Travel Dost utilize a standard smartphone as an onboard IoT GPS tracking unit?
32. **Q4.2**: Why is WebSocket communication preferred over HTTP Polling for real-time bus tracking?
33. **Q4.3**: What is the complete data flow pipeline from the Driver's mobile phone to the Passenger's live map?
34. **Q4.4**: How often are GPS coordinates transmitted from the Driver Dashboard, and why is a 5-second interval chosen?
35. **Q4.5**: How do you run the server locally on shared Wi-Fi so a physical smartphone can connect as a driver device (`0.0.0.0:8000`)?
36. **Q4.6**: How does the Admin Dashboard allow adding, editing, and deleting buses permanently without touching the database manually?
37. **Q4.7**: How does the Single Unified Login system automatically redirect `admin`, `driver1`, and `passenger1` to their respective dashboards?
38. **Q4.8**: What terminal commands are required to set up and start Travel Dost in VS Code from scratch?
39. **Q4.9**: What are the key limitations of the current Travel Dost system, and how can it be enhanced for production deployment?
40. **Q4.10**: Walk through the complete step-by-step Viva demonstration scenario from Admin creation to Driver Start Trip to Passenger Live Tracking.

---

<br><hr><br>

## 📚 SECTION II: DETAILED QUESTIONS & ANSWERS INDEX

---

### PART 1: FRONTEND & UI/UX (HTML5, CSS3, JavaScript, jQuery, Leaflet.js, Bootstrap 5)

#### Q1.1: What frontend technologies and libraries are used in Travel Dost, and why were they chosen over frameworks like React or Angular?
**Answer**:
Travel Dost uses **HTML5**, **Vanilla CSS3**, **JavaScript (ES6+)**, **jQuery 3.7**, **Bootstrap 5.3**, and **Leaflet.js 1.9**.
- **Reason for Choice**: Server-Side Template Rendering via Django Template Language (DTL) coupled with Leaflet.js and jQuery provides immediate page load times, lower memory footprint, zero client-side build pipeline complexities (like Webpack/Babel), and seamless integration with Django session authentication and WebSockets.

#### Q1.2: How does Leaflet.js render interactive maps on the client side, and how is it configured in Travel Dost?
**Answer**:
Leaflet.js is an open-source JavaScript mapping library. It attaches to an HTML `<div>` container (e.g. `<div id="map"></div>`) and fetches map tiles asynchronously from OpenStreetMap servers (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`).
In Travel Dost, it is initialized with center coordinates corresponding to the Hubballi–Dharwad twin city region (`[15.36470, 75.12400]`) at zoom level 13.

#### Q1.3: How are live bus markers dynamically moved on the Leaflet map without reloading or re-initializing the entire map object?
**Answer**:
When a WebSocket `location_update` payload arrives in JavaScript, the callback extracts `latitude` and `longitude`. Instead of re-creating the map, Leaflet provides the `marker.setLatLng(new L.LatLng(lat, lng))` method. Additionally, `map.panTo(newLatLng)` or custom smooth CSS transitions are called to update the marker's position instantly on screen.

#### Q1.4: How does `driver_gps.js` capture the mobile phone's GPS coordinates using the HTML5 Geolocation API (`navigator.geolocation`)?
**Answer**:
`driver_gps.js` checks if `"geolocation" in navigator`. If supported, it calls `navigator.geolocation.getCurrentPosition()` or runs a periodic `setInterval` loop every 5000ms. The callback receives a `position` object containing `position.coords.latitude`, `position.coords.longitude`, `position.coords.speed` (converted from m/s to km/h by multiplying by 3.6), and `position.coords.heading`.

#### Q1.5: What is the difference between `getCurrentPosition()` and `watchPosition()` in the HTML5 Geolocation API?
**Answer**:
- `getCurrentPosition()`: Executes a one-time request to get the device's current location coordinates.
- `watchPosition()`: Registers a handler function that is automatically invoked whenever the device's physical GPS location changes.
In Travel Dost, `driver_gps.js` uses controlled periodic updates (every 5 seconds) to ensure predictable network payload intervals.

#### Q1.6: How is the Viva Indoor Simulation Mode implemented in JavaScript when outdoor GPS signals are unavailable?
**Answer**:
In `driver_gps.js`, a pre-defined array `simWaypoints` contains ordered GPS coordinate objects along the Hubballi-Dharwad highway (KLEIT $\rightarrow$ Vidya Nagar $\rightarrow$ Unkal Lake $\rightarrow$ Navanagar $\rightarrow$ Rayapur $\rightarrow$ Sattur $\rightarrow$ Dharwad CBT). When **Simulate Driving** is checked, `setInterval` iterates through `simWaypoints` every 5 seconds, transmitting simulated latitude, longitude, speed, and heading to the backend.

#### Q1.7: How does jQuery handle AJAX requests for resting API endpoints like `/api/buses/` and `/api/routes/<id>/add-stop/`?
**Answer**:
jQuery's `$.ajax()` method executes asynchronous HTTP requests:
```javascript
$.ajax({
    url: `/api/routes/${routeId}/add-stop/`,
    type: 'POST',
    data: JSON.stringify(payload),
    contentType: 'application/json',
    success: function(response) { /* Update UI */ }
});
```

#### Q1.8: How does `base.html` use Django Template Language (DTL) tags to render conditional navigation links based on user roles?
**Answer**:
`base.html` evaluates DTL boolean tags:
```html
{% if user.is_authenticated and user.is_admin %}
    <!-- Renders Admin Dashboard & Fleet Management Links -->
{% elif user.is_authenticated and user.is_driver %}
    <!-- Renders Driver Dashboard Link -->
{% else %}
    <!-- Renders Passenger Links: Home, Find Route, Live Tracking, Nearby Stops -->
{% endif %}
```

#### Q1.9: What CSS techniques are used for the dark glassmorphism and modern UI aesthetics in Travel Dost?
**Answer**:
- `backdrop-filter: blur(10px)` combined with semi-transparent background colors (`rgba(15, 23, 42, 0.85)`).
- CSS Variables (`:root`) for color palette definitions.
- Custom keyframe animations (`@keyframes pulse`) for the live tracking status badge.
- Rounded container borders (`border-radius: 1rem` / `rounded-4`) and elevated box shadows (`shadow-lg`).

#### Q1.10: How does the Admin Dashboard handle dynamic stop creation on the frontend without refreshing the page?
**Answer**:
In `admin_dashboard.html`, selecting a route triggers a jQuery `GET /api/routes/<id>/` request. The returned route stops array is rendered dynamically into `#stopsList`. Clicking **"Add Stop"** opens a modal, and submitting the form sends a `POST /api/routes/<id>/add-stop/` request, after which `loadRouteStops()` is called to refresh only the stops panel.

---

### PART 2: BACKEND & WEBSOCKETS (Python, Django, Django REST Framework, Django Channels, Algorithms)

#### Q2.1: What is the overall backend architecture of Travel Dost, and what role does Django play in it?
**Answer**:
Travel Dost follows a monolithic, asynchronous-capable Python architecture using **Django 6.0**. Django acts as:
1. Object-Relational Mapper (ORM) for SQLite database interactions.
2. Routing & View controller for UI pages.
3. REST API Provider via Django REST Framework.
4. Real-time WebSocket manager via Django Channels & Daphne.

#### Q2.2: What is the difference between WSGI and ASGI in Python web development, and why does Travel Dost use Daphne/ASGI?
**Answer**:
- **WSGI (Web Server Gateway Interface)**: Synchronous protocol suited for standard HTTP request-response cycles. Blocks worker threads during long-lived connections.
- **ASGI (Asynchronous Server Gateway Interface)**: Asynchronous protocol supporting HTTP, HTTP/2, and persistent bidirectional WebSockets.
- **Choice**: Travel Dost uses **Daphne** (an ASGI server) so it can handle long-lived WebSocket connections for live bus GPS streaming alongside HTTP REST requests.

#### Q2.3: What is Django Channels, and how does it handle WebSockets alongside standard HTTP requests?
**Answer**:
Django Channels extends Django beyond HTTP by replacing default WSGI handlers with ASGI. It inspects incoming connection protocols: HTTP requests are routed to standard URL patterns and Django views, while WebSocket connections (`ws://`) are routed to `routing.py` and handled by `AsyncWebsocketConsumer` classes.

#### Q2.4: How does `BusTrackingConsumer` in `tracking/consumers.py` manage WebSocket connections, message reception, and broadcasting?
**Answer**:
`BusTrackingConsumer` inherits from `AsyncWebsocketConsumer`:
1. `connect()`: Extracts `bus_id` from URL route, accepts the connection, and joins channel groups `bus_<bus_id>` and `bus_all`.
2. `receive(text_data)`: Parses incoming JSON payload from driver, calls `@database_sync_to_async save_bus_location()` to persist to SQLite DB, and triggers `channel_layer.group_send()` to broadcast telemetry to subscribers.
3. `bus_location_broadcast(event)`: Sends location JSON to connected client browser WebSockets.

#### Q2.5: How do Channel Layer Groups work in Django Channels for routing telemetry to specific bus subscribers (`bus_<id>`) and overview subscribers (`bus_all`)?
**Answer**:
Channel Layer Groups act as a pub-sub system. When a passenger views a specific bus map, their WebSocket joins group `bus_101`. When viewing the global overview map, their WebSocket joins group `bus_all`. When `driver1` sends a coordinate for Bus 101, the consumer broadcasts the payload to both `bus_101` and `bus_all` groups simultaneously.

#### Q2.6: How is the Haversine Distance Formula implemented in Python to calculate the distance between geographic GPS coordinates?
**Answer**:
The Haversine formula calculates the great-circle distance between two points on a sphere given their latitudes and longitudes:
$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1) \cdot \cos(\phi_2) \cdot \sin^2\left(\frac{\Delta \lambda}{2}\right)$$
$$c = 2 \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right)$$
$$d = R \cdot c \quad (R = 6371 \text{ km})$$
In `tracking/services/distance.py`, Python's `math.radians`, `sin`, `cos`, `sqrt`, and `atan2` compute distance in kilometers.

#### Q2.7: How does the Intelligent Route Finder algorithm (`tracking/services/route_finder.py`) detect direct and 1-transfer connecting routes?
**Answer**:
1. **Direct Routes**: Queries `RouteStop` to find routes that contain both `source_stop` and `destination_stop` where `stop_order(source) < stop_order(destination)`.
2. **Connecting Routes**: If no direct route exists, finds all routes passing through `source_stop` (Set A) and all routes passing through `destination_stop` (Set B). Finds intersecting `BusStop` nodes (Transfer Hubs) where Route A connects to Route B, calculating total distance and fare.

#### Q2.8: What Django REST Framework (DRF) components (ViewSets, APIViews, Serializers) are used in Travel Dost?
**Answer**:
- **ModelViewSets**: `BusViewSet`, `RouteViewSet`, `BusStopViewSet`, `GPSDeviceViewSet` (provide full CRUD REST endpoints).
- **APIViews**: `RegisterAPIView`, `LoginAPIView`, `RouteSearchAPIView`, `NearbyStopsAPIView`, `BusLocationAPIView`, `AddRouteStopAPIView`.
- **Serializers**: `BusSerializer`, `RouteSerializer`, `BusStopSerializer`, `RouteStopSerializer`, `UserSerializer`.

#### Q2.9: How does `BusLocationAPIView` handle fallback location updates when WebSocket connections are unavailable?
**Answer**:
If WebSocket fails (e.g. strict firewall), `driver_gps.js` posts location payloads to `POST /api/buses/<id>/location/`. `BusLocationAPIView.post()` reads latitude, longitude, speed, heading, updates `Bus.tracking_status = 'LIVE'`, saves a new `BusLocation` record, and returns HTTP 201 Created.

#### Q2.10: How does `database_sync_to_async` work when saving WebSocket telemetry to the SQLite database in asynchronous consumer functions?
**Answer**:
Django's ORM is synchronous. Calling ORM methods inside an asynchronous `async def` function would block the event loop. `@database_sync_to_async` wraps synchronous ORM functions (`BusLocation.objects.create(...)`), running them safely in a background thread pool without stalling WebSocket connections.

---

### PART 3: DATABASE, MIGRATIONS & SECURITY / RBAC (SQLite, Models, Decorators, Sessions)

#### Q3.1: What database engine is used in Travel Dost, and how is the database schema structured?
**Answer**:
Travel Dost uses **SQLite3** (`db.sqlite3`). Schema includes:
- `tracking_user`: Custom user accounts (role, phone_number).
- `tracking_busstop`: Bus stop coordinates (latitude, longitude, area).
- `tracking_route`: Transit route names and start/end points.
- `tracking_routestop`: Junction table linking Route & BusStop with sequence order & distance.
- `tracking_bus`: Bus fleet table linked to Route and driver User.
- `tracking_buslocation`: Historical GPS coordinate logs for buses.

#### Q3.2: How is the custom `User` model implemented by extending Django's `AbstractUser`?
**Answer**:
In `tracking/models.py`:
```python
class User(AbstractUser):
    ROLE_CHOICES = (
        ('USER', 'User'),
        ('PASSENGER', 'Passenger'),
        ('DRIVER', 'Driver'),
        ('ADMIN', 'Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
```
Configured in `settings.py` as `AUTH_USER_MODEL = 'tracking.User'`.

#### Q3.3: How are user roles (`ADMIN`, `DRIVER`, `USER`) defined and validated in the `User` model?
**Answer**:
Model helper methods provide clean role checks:
- `is_admin()`: Returns `True` if `role == 'ADMIN'` or `is_staff` or `is_superuser`.
- `is_driver()`: Returns `True` if `role == 'DRIVER'`.
- `is_user()`: Returns `True` if `role in ['USER', 'PASSENGER']`.

#### Q3.4: How is the relationship between `Bus`, `Route`, `BusStop`, and `RouteStop` defined using Django ForeignKey fields?
**Answer**:
- `RouteStop` has `ForeignKey(Route, on_delete=CASCADE)` and `ForeignKey(BusStop, on_delete=CASCADE)`.
- `Bus` has `ForeignKey(Route, on_delete=SET_NULL, null=True)`.
- Deleting a BusStop cascades to remove related RouteStop entries, while deleting a Route sets `bus.route` to `NULL`.

#### Q3.5: How is the `driver` ForeignKey added to the `Bus` model to enforce that a driver sees ONLY their assigned bus?
**Answer**:
```python
driver = models.ForeignKey(
    User, on_delete=models.SET_NULL, null=True, blank=True,
    limit_choices_to={'role': 'DRIVER'}, related_name='assigned_buses'
)
```
In `driver_portal_view`, the queryset filters `Bus.objects.filter(driver=request.user)`.

#### Q3.6: What are Django Migrations, and what is the difference between `makemigrations` and `migrate`?
**Answer**:
- `python manage.py makemigrations`: Inspects `models.py` changes and creates Python SQL migration instructions in `tracking/migrations/`.
- `python manage.py migrate`: Executes pending migration files against `db.sqlite3` to alter table schemas without losing existing rows.

#### Q3.7: How do custom Python decorators (`@admin_required`, `@driver_required`, `@user_required`) enforce Role-Based Access Control (RBAC)?
**Answer**:
Decorators wrap view functions:
```python
def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_admin():
            return redirect('user-dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
```

#### Q3.8: What happens when an unauthenticated user or user with the wrong role attempts to access `/admin/dashboard/` or `/driver/dashboard/` directly via URL?
**Answer**:
The custom decorator executes before the view function:
1. Unauthenticated user $\rightarrow$ Immediately redirected to `/login/`.
2. Driver attempting to access `/admin/dashboard/` $\rightarrow$ Redirected to `/driver/dashboard/`.
3. User attempting to access `/admin/dashboard/` $\rightarrow$ Redirected to `/dashboard/`.

#### Q3.9: How does Django session-based authentication (`sessionid` cookie) work, and how does `/logout/` flush active sessions?
**Answer**:
Upon successful login, Django generates a random 32-character session key stored in the browser's HTTP cookie (`sessionid`) and saves session data in `django_session` table.
When `/logout/` is visited, `logout(request)` deletes the `sessionid` cookie and deletes the record from `django_session`.

#### Q3.10: What is CSRF (Cross-Site Request Forgery), and how is CSRF protection handled in Django forms and AJAX requests?
**Answer**:
CSRF prevents unauthorized commands from being executed on behalf of an authenticated user. Django embeds a hidden `{% csrf_token %}` token in HTML POST forms. For AJAX requests, jQuery includes `X-CSRFToken` header extracted from `csrftoken` cookie.

---

### PART 4: SYSTEM ARCHITECTURE, IOT GPS TELEMETRY & VIVA DEMO WORKFLOW

#### Q4.1: How does Travel Dost utilize a standard smartphone as an onboard IoT GPS tracking unit?
**Answer**:
The smartphone opens the Driver Dashboard on its web browser. Using the HTML5 Geolocation API (`navigator.geolocation`), the phone acts as an IoT edge node, capturing internal GPS sensor coordinates and transmitting them over Wi-Fi/Cellular networks to the server every 5 seconds.

#### Q4.2: Why is WebSocket communication preferred over HTTP Polling for real-time bus tracking?
**Answer**:
- **HTTP Polling**: Client sends repeated HTTP GET requests every N seconds. Creates huge HTTP header overhead (cookies, headers) and server CPU load.
- **WebSockets**: Establishes a single, persistent full-duplex TCP socket connection. Low latency (<50ms) and minimal overhead per coordinate frame.

#### Q4.3: What is the complete data flow pipeline from the Driver's mobile phone to the Passenger's live map?
**Answer**:
1. Driver Phone captures GPS coordinates via HTML5 Geolocation.
2. Transmits JSON payload over WebSocket (`ws://<host>/ws/bus-tracking/101/`).
3. `BusTrackingConsumer` receives message, calls `save_bus_location()` to update SQLite DB.
4. Consumer calls `channel_layer.group_send("bus_all", ...)` to broadcast telemetry.
5. Passenger's browser WebSocket receives JSON payload.
6. JavaScript invokes `marker.setLatLng([lat, lng])` on Leaflet map.

#### Q4.4: How often are GPS coordinates transmitted from the Driver Dashboard, and why is a 5-second interval chosen?
**Answer**:
Coordinates are sent every **5000 milliseconds (5 seconds)**. This interval balances high map precision (smooth marker motion) with network bandwidth efficiency and battery consumption on the driver device.

#### Q4.5: How do you run the server locally on shared Wi-Fi so a physical smartphone can connect as a driver device (`0.0.0.0:8000`)?
**Answer**:
By running `python manage.py runserver 0.0.0.0:8000`, Django binds to all network interfaces. Devices connected to the same Wi-Fi network open `http://<laptop-ip-address>:8000/login/` to access the site.

#### Q4.6: How does the Admin Dashboard allow adding, editing, and deleting buses permanently without touching the database manually?
**Answer**:
The Admin Dashboard posts HTML forms to:
- `POST /admin/bus/add/`: Calls `Bus.objects.create(...)`.
- `POST /admin/bus/edit/<id>/`: Updates existing `Bus` fields and saves.
- `POST /admin/bus/delete/<id>/`: Calls `bus.delete()`.
All operations update `db.sqlite3` permanently.

#### Q4.7: How does the Single Unified Login system automatically redirect `admin`, `driver1`, and `passenger1` to their respective dashboards?
**Answer**:
`LoginAPIView` authenticates credentials and inspects `user.role`:
- If `ADMIN` $\rightarrow$ returns `"redirect_url": "/admin/dashboard/"`.
- If `DRIVER` $\rightarrow$ returns `"redirect_url": "/driver/dashboard/"`.
- If `USER` / `PASSENGER` $\rightarrow$ returns `"redirect_url": "/dashboard/"`.
Client JS redirects `window.location.href` to `res.redirect_url`.

#### Q4.8: What terminal commands are required to set up and start Travel Dost in VS Code from scratch?
**Answer**:
```powershell
# 1. Activate Virtual Environment
.\venv\Scripts\activate

# 2. Run Database Migrations
python manage.py migrate

# 3. Start Development Server
python manage.py runserver
```

#### Q4.9: What are the key limitations of the current Travel Dost system, and how can it be enhanced for production deployment?
**Answer**:
- **Limitations**: SQLite database (single-file locking under high concurrency), browser reliance for GPS.
- **Production Enhancements**: Replace SQLite with PostgreSQL/PostGIS, deploy with Gunicorn/Daphne behind Nginx, use Redis channel layer, and integrate OBD-II hardware GPS trackers.

#### Q4.10: Walk through the complete step-by-step Viva demonstration scenario from Admin creation to Driver Start Trip to Passenger Live Tracking.
**Answer**:
1. **Admin Login & Creation**: Open `http://127.0.0.1:8000/`, log in as `admin` (`admin123`). In Admin Dashboard, add Bus 101, assign `driver1`, and configure route stops.
2. **Driver Start Trip**: Click **Logout**. Log in as `driver1` (`driver123`). Driver Dashboard opens showing Bus 101. Check **Simulate Driving Mode** and click **START TRIP**. Telemetry starts streaming every 5s.
3. **Passenger Live Map View**: Open a second browser tab to `http://127.0.0.1:8000/tracking/`. Watch the 🚌 Bus 101 marker move live on the Leaflet map in real time without refreshing!
