# ☕ CaféQueue — Smart Restaurant Table Queue & Analytics System

A full-stack intelligent queue management system for restaurants, built using **Flask + MongoDB**, featuring real-time queue handling, analytics, and simulation.

---

## 🚀 Key Features

### 🧠 Core System
- Multi-queue architecture:
  - Ready Queue (FIFO per seat category)
  - Cleaning Queue (FIFO)
  - Priority Queue (VIP + size-based)
- Smart table allocation (exact match → next best fit)
- VIP priority handling
- Automated cleaning → reallocation workflow

---

### 📊 Analytics & Insights (NEW)
- Daily customer trends (date-wise)
- Time-slot distribution (morning, afternoon, evening, night)
- 30-minute interval timeline (continuous traffic curve)
- Peak hour detection
- Real operational data analysis (not static)

---

### 🎲 Monte Carlo Simulation (NEW)
- Predict wait times and throughput
- Uses **real historical data** (not manual input)
- Computes:
  - Average wait time
  - P95 wait time
  - Throughput
  - Occupancy rate
- Provides intelligent recommendations

---

### 🔐 Authentication System (NEW)
- Login / Register system
- Admin & Staff roles
- Secure password hashing (salted SHA-256)

---

### 👤 Profile Management (NEW)
- Users can update:
  - Full name
  - Username
  - Password
- Session updates dynamically
- Secure validation & uniqueness checks

---

### ⚡ Real-Time Dashboard (NEW)
- Auto-refresh every 5 seconds
- Live stats:
  - Ready tables
  - Occupied tables
  - Cleaning tables
  - Waiting customers
- No manual refresh needed

---

### 🎨 UI/UX Enhancements
- Premium dark theme
- Glassmorphism cards
- Futuristic login typography (custom font)
- Smooth hover + transitions
- Clean dashboard layout

---

## 📸 Pages Overview

| Page | URL | Purpose |
|---|---|---|
| Dashboard | `/` | Live stats, table map, active orders |
| Orders | `/orders` | Place orders & allocate tables |
| Cleaning | `/cleaning` | Manage cleaning workflow |
| Queues | `/queues` | View all queues |
| Analytics | `/analytics` | Data insights & trends |
| History | `/history` | Order history |
| Logs | `/logs` | System audit logs |
| Setup | `/setup` | Initialize tables |
| Users | `/users` | Admin user management |
| Login | `/login` | Authentication |
| Register | `/register` | Create account |

---

## ⚙️ Queue Algorithms

### 1. Ready Queue
- FIFO per seat size
- Tables added after cleaning or setup
- Dequeued on allocation

---

### 2. Cleaning Queue
- Triggered after payment
- FIFO structure
- After cleaning:
  - Allocates to waiting customer OR
  - Moves to ready queue

---

### 3. Priority Queue
- Sorted by:
  1. VIP
  2. Larger groups first
  3. FIFO within same priority

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python 3.10+) |
| Database | MongoDB (PyMongo) |
| Frontend | HTML, CSS, Vanilla JS |
| Auth | Session-based + hashed passwords |
| Analytics | Custom aggregation + simulation |

---
