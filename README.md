<div align="center">

# ☕ CaféQueue

### Intelligent Restaurant Queue & Analytics Platform

Real-time queue management, smart table allocation, analytics, and Monte Carlo simulation — engineered for modern cafés and restaurants.

<br>

<p>
  <a href="https://cafequeue.onrender.com">
    <img src="https://img.shields.io/badge/Live-Demo-ff6b35?style=for-the-badge&logo=render&logoColor=white"/>
  </a>
  <img src="https://img.shields.io/badge/Flask-Backend-black?style=for-the-badge&logo=flask"/>
  <img src="https://img.shields.io/badge/MongoDB-Database-green?style=for-the-badge&logo=mongodb"/>
  <img src="https://img.shields.io/badge/Monte-Carlo-Simulation-blue?style=for-the-badge"/>
</p>

</div>

---

## ⚡ Platform Highlights

🧠 Smart Table Allocation  
📊 Real-Time Analytics  
🎲 Monte Carlo Simulation  
⚡ Live Queue Management  
🔐 Role-Based Authentication  

---
# ✨ Product Showcase

## 🔥 Premium Login Experience

<p align="center">
  <img src="./Login.png" width="95%">
</p>

---

## 📊 Live Operations Dashboard

<p align="center">
  <img src="./Cafe Dashboard.png" width="95%">
</p>

---

# ⚡ Platform Preview

<p align="center">
  <img src="./Cafe Analytics.png" width="95%">
</p>

<p align="center">
  <i>Real-time queue intelligence, analytics and simulation engineered for modern cafés.</i>
</p>

---
## 📑 Table of Contents

- [📸 Preview](#-preview)
- [🚀 Key Features](#-key-features)
- [📊 Analytics & Insights](#-analytics--insights-new)
- [🎲 Monte Carlo Simulation](#-monte-carlo-simulation-new)
- [⚙️ Queue Algorithms](#️-queue-algorithms)
- [🛠 Tech Stack](#-tech-stack)
## 🚀 Key Features

# 🚀 Core System & Intelligence

## 🧠 Queue Intelligence Engine

<table>
<tr>
<td width="50%">

### Queue Inspector
Multi-queue architecture with:

✔ Ready Queue (FIFO)  
✔ Cleaning Queue  
✔ Priority Queue (VIP + size-based)

<img src="./Queues.png" width="100%">

</td>

<td width="50%">

### Smart Restaurant Setup
Configure seating layouts and initialize operations with live preview.

<img src="./Restaurant setup.png" width="100%">

</td>
</tr>
</table>

---

## 📈 Real-Time Analytics

Advanced operational intelligence powered by real restaurant data.

<table>
<tr>
<td width="50%">

### Daily Analytics
Customer trends, peak-hour detection and traffic curves.

<img src="./Daily Analytics.png" width="100%">

</td>

<td width="50%">

### Analytics Dashboard
Date-wise operational insights and business intelligence.

<img src="./Cafe Analytics.png" width="100%">

</td>
</tr>
</table>

---

## 🎲 Monte Carlo Simulation

Predict restaurant performance using historical operational patterns.

<img src="./Monte Carlo.png" width="100%">

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

# 🧠 Queue Architecture

CaféQueue uses a multi-queue architecture designed for intelligent restaurant operations and efficient customer handling.

<table>
<tr>
<td width="33%">

## Ready Queue

FIFO queue organized by seat category.

- Exact seating match
- Fast allocation
- Auto refill after cleaning

</td>

<td width="33%">

## Cleaning Queue

Dedicated FIFO cleaning workflow.

- Triggered after payment
- Cleaning lifecycle tracking
- Auto transition to ready state

</td>

<td width="33%">

## Priority Queue

Priority-based allocation engine.

- VIP customers
- Large groups prioritized
- FIFO inside same priority

</td>
</tr>
</table>

---

# ⚙️ Smart Allocation Logic

CaféQueue follows a layered allocation strategy:

```text
Customer Arrival
        ↓
Priority Evaluation
        ↓
Exact Table Match
        ↓
Next Best Fit Allocation
        ↓
Queue Placement
        ↓
Dining → Cleaning → Ready Queue
```

This workflow minimizes wait times and improves operational efficiency.

---
---

# 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python 3.10+) |
| Database | MongoDB + PyMongo |
| Frontend | HTML5, CSS3, Vanilla JS |
| Authentication | Session-based + SHA-256 hashing |
| Analytics | Custom aggregation + Monte Carlo simulation |

---

# 🚀 Run Locally

Clone the project:

```bash
git clone <repo-url>
cd CafeQueue
pip install -r requirements.txt
```

Configure environment variables:

```env
MONGO_URI=your_mongodb_uri
SECRET_KEY=your_secret_key
FLASK_ENV=development
```

Run:

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

---

# ☕ Final Note

Built with Flask, MongoDB and systems-thinking for smarter restaurant operations.

---
