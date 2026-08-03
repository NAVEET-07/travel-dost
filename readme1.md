# TRAVEL DOST — Complete Easy Project Guide (README 1)

Welcome to **Travel Dost**! This document (`readme1.md`) contains **all the necessary information** in clear, simple, step-by-step language so you can easily understand, run, and present your project.

---

## 📌 1. Project Overview & Mandatory Login-First Security

**Travel Dost** is a real-time bus tracking and travel assistance system built for the **Hubballi–Dharwad twin cities (NWKRTC / Chigari BRTS)** in Karnataka, India.

### 🔒 Login-First Experience:
- **All browser sessions have been cleared.**
- When you open ANY URL (`http://127.0.0.1:8000/`, `http://127.0.0.1:8000/driver/`, `http://127.0.0.1:8000/admin/dashboard/`, etc.), the system checks if you are logged in.
- Because you are not logged in yet, it goes **DIRECTLY to the Login Page** (`http://127.0.0.1:8000/login/`) showing ONLY the Login card!
- Nothing about the project is shown until you enter valid credentials and log in.

---

## 🔑 2. Ready-to-Use Test Accounts & Credentials

Enter any of these accounts in the single login box:

| Role | Username | Password | Required Page Opened Upon Login |
| :--- | :--- | :--- | :--- |
| **System Admin** | `admin` | `admin123` | **Admin Dashboard** (`/admin/dashboard/`) |
| **Bus Driver** | `driver1` | `driver123` | **Driver Dashboard** (`/driver/dashboard/`) |
| **User / Passenger** | `passenger1` | `passenger123` | **User Dashboard** (`/dashboard/`) |
| **User / Passenger** | `user1` | `user123` | **User Dashboard** (`/dashboard/`) |

---

## 🔗 3. All Exact URLs for Your Laptop

- **Main Login Page**: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/) (or [http://127.0.0.1:8000/](http://127.0.0.1:8000/))
- **Admin Dashboard**: [http://127.0.0.1:8000/admin/dashboard/](http://127.0.0.1:8000/admin/dashboard/)
- **Driver Dashboard**: [http://127.0.0.1:8000/driver/dashboard/](http://127.0.0.1:8000/driver/dashboard/)
- **User Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- **Live Bus Tracking Map**: [http://127.0.0.1:8000/tracking/](http://127.0.0.1:8000/tracking/)
- **Instant Logout Link**: [http://127.0.0.1:8000/logout/](http://127.0.0.1:8000/logout/)

---

## 🚪 4. How to Logout & Switch Accounts

If you want to log out of `driver1` and log in as `admin`:

1. Click **`Logout`** in the top navigation bar or visit [http://127.0.0.1:8000/logout/](http://127.0.0.1:8000/logout/).
2. You will immediately be taken back to the Login page.
3. Type `admin` & `admin123` to open the Admin Dashboard!

---

## 🚀 5. Step-by-Step VS Code Run Guide

### Step 1: Open VS Code
1. Open Visual Studio Code.
2. Select **File → Open Folder...**
3. Choose `c:\Users\NAVEET\Documents\TRAVLE DOTS`.
4. Open the integrated terminal: Press `Ctrl + ~`.

### Step 2: Activate Virtual Environment
```powershell
.\venv\Scripts\activate
```

### Step 3: Start Server
```powershell
python manage.py runserver
```

---

## 🛡️ 6. How the Admin Dashboard Works

When logged in as `admin`:

1. **Add New Bus**: Click **`+ Add New Bus`** button $\rightarrow$ enter bus number & details $\rightarrow$ click **Save Bus**.
2. **Edit Bus**: Click **`Edit`** next to any bus in the table to modify details or reassign driver.
3. **Delete Bus**: Click **`Delete`** next to any bus in the table to remove it permanently from database.
4. **Dynamic Route Stops Manager**: Select a route on the right panel and click **`+ Add Stop`** to add bus stops.

---

## 🚌 7. How Driver & Live Map Tracking Work

1. Log in as `driver1` $\rightarrow$ Driver Dashboard opens showing **Bus 101 ONLY**.
2. Click **`START TRIP`** $\rightarrow$ GPS coordinates transmit every 5 seconds.
3. Open [http://127.0.0.1:8000/tracking/](http://127.0.0.1:8000/tracking/) $\rightarrow$ Watch the bus marker move live on the Leaflet map in real time!
