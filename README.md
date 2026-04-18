# ☕ CaféQueue — Restaurant Table Queue Management System

A full-stack web application implementing the complete queue workflow for café/restaurant table allocation — built with **Python Flask**, **MongoDB**, and a dark premium UI.

---

## 📸 Pages Overview

| Page | URL | Purpose |
|---|---|---|
| Dashboard | `/` | Live stats, table map, quick order, active orders, priority queue |
| New Order | `/orders` | Place orders, view available tables, manage priority queue |
| Cleaning | `/cleaning` | Mark tables as cleaned, see ready/waiting queues |
| Queues | `/queues` | Inspect all three queues in real time |
| History | `/history` | Full order history with filtering and durations |
| Logs | `/logs` | Audit trail of every system action |
| Setup | `/setup` | Initialize restaurant with table config |

---

## ⚙️ Queue Algorithms Implemented

### 1. Ready Queue (FIFO per seat category)
- One FIFO queue per seat size: 2, 4, 6, 8, 10
- Tables enqueued at setup; dequeued on customer arrival
- **Enqueue:** restaurant setup, or after a table is cleaned with no waiting customers
- **Dequeue:** when a customer arrives requesting that seat count

### 2. Cleaning Queue (FIFO per seat category)
- Same structure as ready queue
- **Enqueue:** triggered automatically when payment is processed
- **Dequeue:** when staff clicks "Mark Cleaned"
- After dequeue: checks priority queue → allocates if match found, else returns to ready queue

### 3. Priority Queue (sorted by priority key)
- **Enqueue:** when no matching table is available at arrival time
- **Dequeue:** when a cleaned table becomes available
- **Priority order:**

| Priority | Customer Type |
|---|---|
| 0 — Highest | VIP (checkbox enabled) |
| 1 | 10-seat group |
| 2 | 8-seat group |
| 3 | 6-seat group |
| 4 | 4-seat group |
| 5 — Lowest | 2-seat group |

- Ties within same priority are broken by arrival time (FIFO)

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.x |
| Database | MongoDB (PyMongo driver) |
| Frontend | HTML5, CSS3 (custom dark theme), Vanilla JavaScript |
| Fonts | Syne (headings), Inter (body), JetBrains Mono (code) |

---

## 📁 Project Structure

```
cafequeue/
├── app.py                   # Flask app — all routes and business logic
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── static/
│   ├── css/
│   │   └── app.css          # Complete stylesheet (dark theme, components)
│   └── js/
│       └── app.js           # Shared JS: API helper, toast, time formatters
└── templates/
    ├── base.html            # Base layout — sidebar, topbar, live clock
    ├── dashboard.html       # Main dashboard
    ├── setup.html           # Table configuration
    ├── orders.html          # Order placement
    ├── cleaning.html        # Cleaning station
    ├── queues.html          # Queue inspector
    ├── history.html         # Order history
    └── logs.html            # Activity logs
```

---

## ✅ Prerequisites

### 1. Python 3.10+
```bash
python --version
# Should show Python 3.10.x or higher
```

### 2. MongoDB Community Server
Download: https://www.mongodb.com/try/download/community

Verify MongoDB is installed:
```bash
mongod --version
```

### 3. pip (comes with Python)
```bash
pip --version
```

---

## 🚀 Execution Sequence

Follow every step in order.

---

### STEP 1 — Extract the project

```bash
unzip cafequeue.zip
cd cafequeue
```

---

### STEP 2 — Create a virtual environment

```bash
# Create virtual environment
python -m venv venv
```

Activate it:

```bash
# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

You should see `(venv)` in your terminal prompt.

---

### STEP 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `flask==3.0.3` — web framework
- `pymongo==4.8.0` — MongoDB driver
- `python-dotenv==1.0.1` — environment variable loader

---

### STEP 4 — Configure environment (optional)

```bash
cp .env.example .env
```

Edit `.env` if your MongoDB is on a different host or port. Default config works for a standard local MongoDB installation:

```
MONGO_URI=mongodb://localhost:27017/
```

---

### STEP 5 — Start MongoDB

MongoDB must be running before you start Flask.

```bash
# macOS (Homebrew)
brew services start mongodb-community

# Ubuntu / Debian
sudo systemctl start mongod

# Windows (run Command Prompt as Administrator)
net start MongoDB
```

Verify MongoDB is running:
```bash
# Should connect without error
mongosh
# Type 'exit' to quit the shell
```

---

### STEP 6 — Run the Flask application

```bash
python app.py
```

Expected output:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
 * Restarting with stat
 * Debugger is active!
```

---

### STEP 7 — Open in your browser

Navigate to: **http://localhost:5000**

You will see the Dashboard. It will show empty queues until you initialize the restaurant.

---

### STEP 8 — Initialize the restaurant (required first step)

1. Click **Setup** in the left sidebar
2. Click one of the preset buttons:
   - **☕ Small Café** — 8 tables (recommended for first run)
   - **🍴 Medium Restaurant** — 16 tables
   - **🏨 Large Venue** — 20 tables
3. Or add tables manually using "+ Add Table"
4. Click **🚀 Initialize Restaurant**
5. You'll be redirected to the Dashboard with all tables in **Ready** state

---

### STEP 9 — Test the complete workflow

#### Scenario: Full workflow test

**Step A — Seat customers:**
1. Go to **New Order** (`/orders`)
2. Enter "Alice", 4 seats → click **Allocate Table** → gets T5 (or similar)
3. Enter "Bob", 4 seats → click **Allocate Table** → gets another 4-seat table
4. Enter "Charlie", 4 seats, check ⭐ VIP → click **Allocate Table** → no 4-seat tables left, added to priority queue
5. Enter "Diana", 4 seats → also added to priority queue

**Step B — Process payment:**
1. Go to **Dashboard** (`/`)
2. Find Alice's order in "Active Orders"
3. Click **💳 Pay & Clear** → Alice's table moves to Cleaning Queue

**Step C — Clean the table:**
1. Go to **Cleaning** (`/cleaning`)
2. Find Alice's table in the cleaning queue
3. Click **✓ Mark Cleaned**
4. Since Charlie (VIP, priority 0) is waiting, the table is allocated to Charlie automatically

**Step D — Verify:**
1. Go to **Queues** (`/queues`) — see all three queues live
2. Go to **History** (`/history`) — see all orders with durations
3. Go to **Logs** (`/logs`) — see the full audit trail

---

## 🔌 API Reference

All endpoints return JSON.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/setup` | Initialize restaurant with table definitions |
| `GET` | `/api/tables` | Get all tables with current status |
| `GET` | `/api/stats` | Get summary counts |
| `GET` | `/api/ready-queue` | Get ready queues grouped by seat count |
| `GET` | `/api/cleaning-queue` | Get cleaning queues grouped by seat count |
| `GET` | `/api/priority-queue` | Get priority queue sorted by priority |
| `GET` | `/api/orders` | Get all orders |
| `GET` | `/api/orders/active` | Get active orders only |
| `POST` | `/api/orders/new` | Place new order / allocate table |
| `POST` | `/api/orders/<id>/pay` | Mark order paid → send to cleaning |
| `POST` | `/api/cleaning/<id>/cleaned` | Mark table cleaned → allocate or ready |
| `GET` | `/api/logs` | Get last 100 log entries |

### POST /api/setup
```json
{
  "tables": [
    { "number": "T1", "seats": 2 },
    { "number": "T2", "seats": 4 }
  ]
}
```

### POST /api/orders/new
```json
{
  "name": "Priya Sharma",
  "seats": 4,
  "is_vip": false
}
```

---

## 🗄 MongoDB Collections

| Collection | Contents |
|---|---|
| `tables` | All tables — number, seats, status (ready/occupied/cleaning), current order ID |
| `ready_queues` | FIFO ready queue entries — table_id, seats, enqueued timestamp |
| `cleaning_queues` | FIFO cleaning queue entries — same structure as ready_queues |
| `priority_queue` | Waiting customers — name, seats, is_vip, priority key, enqueued timestamp |
| `orders` | All orders — customer info, table_id, status, timestamps |
| `logs` | Audit log — action, detail, timestamp |

Database name: `cafequeue_db`

---

## 🐛 Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Dependencies not installed | Run `pip install -r requirements.txt` with venv active |
| `pymongo.errors.ServerSelectionTimeoutError` | MongoDB not running | Start MongoDB (Step 5) |
| `Address already in use` on port 5000 | Another app using port 5000 | Change `port=5000` to `port=5001` in `app.py` last line |
| Tables not showing on dashboard | Restaurant not initialized | Go to `/setup` and click Initialize |
| Fonts not loading | No internet connection | App works fine without fonts, just uses system fallback |
| `venv\Scripts\Activate.ps1 cannot be loaded` (Windows) | PowerShell execution policy | Run: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

---

## 📝 Notes

- The UI auto-refreshes every 8–15 seconds depending on the page
- MongoDB database and collections are created automatically on first run
- Re-running Setup resets **all data** — tables, orders, queues, and logs
- No login/authentication — designed as a staff-facing internal tool
- Works on any modern browser (Chrome, Firefox, Edge, Safari)

