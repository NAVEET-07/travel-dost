# TRAVEL DOST — Smart Bus Tracking & Travel Assistance System

**B.E. Computer Science Engineering Major Project**

* **Project Title:** Travel Dost — Smart Bus Tracking & Travel Assistance System
* **Domain:** Web Application / Real-Time Systems / IoT & GIS Transport Logistics
* **Target Region:** Hubballi–Dharwad Twin Cities, Karnataka, India (NWKRTC & Chigari BRTS)
* **Tagline:** *"Your Smart Companion for Bus Travel."*
* **Core Innovation:** Role-Based Transit Management with Real-Time GPS Bus Tracking over WebSockets & Intelligent Route Finding.

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Role-Based Access Control (RBAC)](#-role-based-access-control-rbac)
3. [Exact Role Access URLs](#-exact-role-access-urls)
4. [Technology Stack](#-technology-stack)
5. [System Requirements](#-system-requirements)
6. [Step-by-Step Execution Guide (VS Code)](#-step-by-step-execution-guide-vs-code)
7. [Default Test Accounts & Credentials](#-default-test-accounts--credentials)
8. [End-to-End Application Workflow](#-end-to-end-application-workflow)
9. [Project Folder Structure & Modified Files](#-project-folder-structure--modified-files)
10. [REST API Documentation](#-rest-api-documentation)
11. [Real-Time WebSocket Architecture](#-real-time-websocket-architecture)

---

## 📌 Project Overview

**Travel Dost** is a full-stack, real-time public transit tracking and route recommendation system built specifically for commuters in the **Hubballi–Dharwad twin cities of Karnataka, India**.

In public transportation networks like **NWKRTC (North Western Karnataka Road Transport Corporation)**, passengers frequently experience long wait times and uncertainty regarding bus arrival times, current location, bus numbers, fares, and optimal transfer points.

**Travel Dost** solves this by providing:
1. **Role-Based Portals**: Dedicated, isolated environments for System Administrators, Drivers, and Passengers.
2. **Driver GPS Transmitter**: A driver's smartphone or device streams live GPS coordinates every 5 seconds to a Django backend over WebSockets/REST APIs.
3. **Real-Time Live Map**: Passengers watch moving bus markers on an interactive Leaflet/OpenStreetMap without reloading pages.
4. **Intelligent Route Finder**: Automatically finds direct and connecting bus routes based on source and destination stops.

---

## 🔐 Role-Based Access Control (RBAC)

Travel Dost enforces strict separation of concerns through three distinct user roles:

### 1. 🛡️ Admin Role
- **Access**: Strictly restricted to system administrators (`role == 'ADMIN'` or superusers).
- **Features**:
  - Full CRUD operations for Buses (Add, Edit, Delete buses directly from UI).
  - Assign drivers to specific buses.
  - **Dynamic Route Stops Manager**: Dynamically add, reorder, edit, or delete stops for any route using an **"Add Stop"** button in real time.
  - Permanent database persistence (`db.sqlite3`) without manual database editing.

### 2. 🚌 Driver Role
- **Access**: Restricted to bus drivers (`role == 'DRIVER'`). Direct URL access to admin or user pages is blocked.
- **Features**:
  - Driver views **ONLY** their assigned bus (e.g. Bus 101 assigned to `driver1`).
  - Access to bus/route management is removed.
  - Includes **Start Trip** and **Stop Trip** control buttons.
  - **Start Trip**: Requests browser location permissions and continuously transmits GPS coordinates (latitude, longitude, speed, heading, timestamp, bus ID) to the backend every 5 seconds. Includes an indoor Viva simulation mode for demonstrations.
  - **Stop Trip**: Halts location updates and marks bus status as `OFFLINE`.
  - Interactive Leaflet map preview showing live location telemetry.

### 3. 👤 User / Passenger Role
- **Access**: Accessible by registered passengers (`role == 'USER'` / `'PASSENGER'`) or public visitors.
- **Features**:
  - Search buses (`/find-route/`)
  - View bus routes (`/routes/`)
  - View bus stops (`/stops/`)
  - View fare matrices
  - Track buses live on the interactive map (`/tracking/`)
  - **Never sees any Admin or Driver management controls**.

---

## 🔗 Exact Role Access URLs

| Portal / Role | Exact URL | Description |
| :--- | :--- | :--- |
| **Admin Login** | `http://127.0.0.1:8000/admin/login/` | Dedicated login page for system administrators. |
| **Admin Dashboard** | `http://127.0.0.1:8000/admin/dashboard/` | Operations center: Bus CRUD, driver assignment & dynamic route stops. |
| **Driver Login** | `http://127.0.0.1:8000/driver/login/` | Dedicated login page for bus drivers. |
| **Driver Dashboard** | `http://127.0.0.1:8000/driver/dashboard/` | Displays assigned bus, Start/Stop Trip buttons & 5-sec GPS streaming. |
| **User Login** | `http://127.0.0.1:8000/login/` | Sign-in page for passengers. |
| **User Registration** | `http://127.0.0.1:8000/register/` | Public registration page for passengers. |
| **User Dashboard** | `http://127.0.0.1:8000/dashboard/` | Passenger portal for searching routes, stops, fares & live tracking. |
| **Live Bus Tracking Map** | `http://127.0.0.1:8000/tracking/` | Real-time Leaflet map displaying active moving bus markers. |

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | Python 3.10+, Django 6.0, Django REST Framework (DRF) |
| **Real-Time Layer** | Django Channels 4.3, WebSockets, ASGI (Daphne / AsyncWebsocketConsumer) |
| **Frontend UI** | HTML5, Vanilla CSS3 (Glassmorphism), JavaScript (jQuery, Bootstrap 5) |
| **Mapping Engine** | Leaflet.js 1.9, OpenStreetMap Tile Layers |
| **Database** | SQLite (`db.sqlite3`) |
| **Testing** | Django Unit Test Runner |

---

## 💻 System Requirements

- **Operating System:** Windows 10/11, macOS, or Linux.
- **Python Version:** Python **3.10, 3.11, or 3.12** installed and added to PATH.
- **Code Editor:** Visual Studio Code (VS Code).
- **Browser:** Chrome, Edge, Firefox, or Safari with Geolocation and WebSockets enabled.

---

## 🚀 Step-by-Step Execution Guide (VS Code)

Follow these exact steps to run the project in Visual Studio Code:

### Step 1: Open Project in VS Code
1. Open VS Code.
2. Select **File $\rightarrow$ Open Folder...** and choose `c:\Users\NAVEET\Documents\TRAVLE DOTS`.
3. Open a new terminal: `Ctrl + ~` (or **Terminal $\rightarrow$ New Terminal**).

### Step 2: Create & Activate Virtual Environment
```powershell
# Create a virtual environment named 'venv'
python -m venv venv

# Activate virtual environment on Windows PowerShell
.\venv\Scripts\activate
```

> **Why this command?**
> `python -m venv venv` creates an isolated Python directory so project dependencies don't conflict with global software. `.\venv\Scripts\activate` switches terminal execution to use the project's virtual environment.

### Step 3: Install Required Dependencies
```powershell
pip install django djangorestframework channels channels-redis daphne
```

> **Why this command?**
> Installs Django framework, REST framework APIs, Channels for WebSocket handling, and Daphne ASGI server for real-time streaming.

### Step 4: Apply Database Migrations
```powershell
# Create migration files for model changes
python manage.py makemigrations

# Apply migrations to db.sqlite3
python manage.py migrate
```

> **Why this command?**
> Scans `tracking/models.py` (e.g. for `driver` assignment field on `Bus`) and safely updates the SQLite database without deleting existing data.

### Step 5: Start the Development Server
```powershell
python manage.py runserver
```

> **Why this command?**
> Starts the Django web server on `http://127.0.0.1:8000/`. You can now open any of the role URLs in your browser!

---

## 🔑 Default Test Accounts & Credentials

The SQLite database (`db.sqlite3`) comes pre-seeded with test accounts:

| Role | Username | Password | Assigned Resource / Access |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `admin` | `admin123` | Full Admin Dashboard (`/admin/dashboard/`) & Django Admin |
| **Bus Driver** | `driver1` | `driver123` | Driver Dashboard (`/driver/dashboard/`) assigned to **Bus 101** |
| **User / Passenger** | `passenger1` | `passenger123` | User Dashboard (`/dashboard/`) & Live Tracking (`/tracking/`) |
| **User / Passenger** | `user1` | `user123` | Passenger search, stops, fares & tracking |

---

## 🔄 End-to-End Application Workflow

```text
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│     ADMIN PORTAL       │      │     DRIVER PORTAL      │      │     PASSENGER PORTAL   │
│ http://.../admin/login/│      │http://.../driver/login/│      │ http://.../tracking/   │
└───────────┬────────────┘      └───────────┬────────────┘      └───────────┬────────────┘
            │                               │                               │
 1. Adds Bus & assigns           2. Logs in & clicks             3. Opens Live Tracking
    Driver1 to Bus 101              "START TRIP"                    Map on laptop/phone
            │                               │                               │
 2. Dynamically adds stops       3. Sends GPS location           4. Sees Bus 101 marker
    via "Add Stop" button           every 5 seconds                 moving in real-time
            │                               │                               │
            ▼                               ▼                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Django Backend & WebSockets                              │
│         Stores BusLocation in DB & Broadcasts via BusTrackingConsumer                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Admin Creation**: Admin logs in at `/admin/login/`, accesses `/admin/dashboard/`, creates a new Bus (e.g. Bus 101), assigns `driver1` as its driver, and dynamically adds intermediate stops using the **"Add Stop"** button.
2. **Driver Transmission**: `driver1` logs into `/driver/login/`, reaching `/driver/dashboard/`. The driver sees **only Bus 101** and clicks **START TRIP**. The browser requests location access (or uses simulation mode) and sends GPS latitude, longitude, timestamp, and speed to the backend every 5 seconds.
3. **Real-Time Location Broadcast**: Django receives the GPS payload, updates `BusLocation` in `db.sqlite3`, sets bus status to `LIVE`, and broadcasts the update via WebSockets.
4. **Passenger Live Map View**: Passengers open `/tracking/`. Leaflet map receives the WebSocket broadcast and updates the marker position for Bus 101 in real time!

---

## 📁 Project Folder Structure & Modified Files

```text
TRAVLE DOTS/
├── db.sqlite3                  # SQLite Database (All data preserved permanently)
├── manage.py                   # Django CLI Management Script
├── templates/                  # Frontend HTML Templates
│   ├── base.html               # Base layout with role-based navbar
│   ├── admin_login.html        # Admin Login Page (/admin/login/)
│   ├── admin_dashboard.html    # Admin Dashboard with Bus CRUD & Dynamic Stops
│   ├── driver_login.html       # Driver Login Page (/driver/login/)
│   ├── driver_portal.html      # Driver Dashboard with Start/Stop Trip controls
│   ├── login.html              # User Login Page (/login/)
│   ├── register.html           # User Registration Page (/register/)
│   ├── user_dashboard.html     # User Passenger Dashboard (/dashboard/)
│   ├── live_tracking.html      # Live Bus Map (/tracking/)
│   └── route_finder.html       # Intelligent Route Finder
├── tracking/                   # Main Django App
│   ├── decorators.py           # Custom RBAC decorators (@admin_required, @driver_required, @user_required)
│   ├── models.py               # Database Models (User, Bus, Route, BusStop, RouteStop, GPSDevice)
│   ├── views_ui.py             # Role-protected UI view handlers
│   ├── views_api.py            # REST API endpoints (Auth, Bus CRUD, Dynamic Stops, Telemetry)
│   ├── serializers.py          # DRF Serializers
│   ├── urls.py                 # App URL routing
│   ├── consumers.py            # WebSockets Live Tracking Consumer
│   └── migrations/             # Database Migration Files
│       ├── 0001_initial.py
│       └── 0002_bus_driver_alter_user_role.py
├── static/                     # Static CSS & JS Assets
│   ├── css/style.css
│   └── js/driver_gps.js        # Driver 5-sec GPS transmitter & Leaflet map preview logic
├── travel_dost_backend/        # Django Project Root Configuration
│   ├── settings.py             # Settings & Channels ASGI config
│   ├── urls.py                 # Main URL router
│   └── asgi.py                 # ASGI entry point for Daphne/WebSockets
└── venv/                       # Python Virtual Environment
```

---

## 📄 REST API Documentation

| Endpoint | Method | Permission | Description |
| :--- | :--- | :--- | :--- |
| `/api/auth/register/` | `POST` | Public | Register new User or Driver account |
| `/api/auth/login/` | `POST` | Public | User login endpoint returning role-based redirect URL |
| `/api/auth/logout/` | `POST` | Authenticated | Logout current user session |
| `/api/buses/` | `GET`, `POST` | Public / Admin | List all active buses or create a new bus |
| `/api/buses/<id>/` | `PATCH`, `DELETE` | Admin | Edit bus details/driver or delete bus |
| `/api/routes/<id>/add-stop/` | `POST` | Admin | Dynamically add a stop to a route |
| `/api/route-stops/<id>/delete/` | `DELETE` | Admin | Remove a stop from a route |
| `/api/search-route/?source=<id>&destination=<id>` | `GET` | Public | Calculate best direct & connecting routes |
| `/api/nearby-stops/?lat=<lat>&lng=<lng>` | `GET` | Public | Find nearest bus stops using Haversine algorithm |
| `/api/buses/<id>/location/` | `GET`, `POST` | Public | Submit live GPS location or fetch current position |

---

## 📡 Real-Time WebSocket Architecture

* **WebSocket URI:** `ws://<host>/ws/bus-tracking/<bus_id>/`
* **Consumer:** `BusTrackingConsumer` (`tracking/consumers.py`)
* **Payload Format:**
```json
{
  "action": "location_update",
  "bus_id": 101,
  "latitude": 15.36470,
  "longitude": 75.12400,
  "speed": 35.5,
  "heading": 180.0,
  "status": "LIVE"
}
```

---

## 🎓 Project Credits

* **System Name:** Travel Dost — Smart Bus Tracking & Travel Assistance System
* **Academic Program:** B.E. Computer Science Engineering Major Project
* **Region:** Hubballi–Dharwad, Karnataka, India
* **Year:** 2026
