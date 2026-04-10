from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ── MongoDB Connection ────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["cafequeue_db"]

tables_col        = db["tables"]
ready_queues_col  = db["ready_queues"]
clean_queues_col  = db["cleaning_queues"]
priority_col      = db["priority_queue"]
orders_col        = db["orders"]
logs_col          = db["logs"]

# ── Indexes for performance ───────────────────────────────────────────────────
def ensure_indexes():
    """Create indexes on startup for better query performance"""
    tables_col.create_index([("status", 1), ("number", 1)], background=True)
    tables_col.create_index("order_id", background=True)
    
    ready_queues_col.create_index([("seats", 1), ("enqueued", 1)], background=True)
    clean_queues_col.create_index([("seats", 1), ("enqueued", 1)], background=True)
    
    priority_col.create_index([("priority", 1), ("enqueued", 1), ("seats", 1)], background=True)
    priority_col.create_index([("is_vip", 1)], background=True)
    
    orders_col.create_index([("status", 1), ("created", -1)], background=True)
    orders_col.create_index("table_id", background=True)
    
    logs_col.create_index([("ts", -1)], background=True)

ensure_indexes()

# ── Priority Map (lower = higher priority) ────────────────────────────────────
PRIORITY_MAP = { "vip": 0, 10: 1, 8: 2, 6: 3, 4: 4, 2: 5 }

# ── Helpers ───────────────────────────────────────────────────────────────────
def s(doc):
    if not doc: return None
    doc["_id"] = str(doc["_id"])
    return doc

def log(action, detail=""):
    logs_col.insert_one({
        "action": action, "detail": detail,
        "ts": datetime.utcnow().isoformat()
    })

def now():
    return datetime.utcnow().isoformat()

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/setup", methods=["POST"])
def api_setup():
    data   = request.json
    tables = data.get("tables", [])
    if not tables:
        return jsonify({"ok": False, "msg": "No tables provided"}), 400

    for col in [tables_col, ready_queues_col, clean_queues_col, priority_col, orders_col, logs_col]:
        col.delete_many({})

    for t in tables:
        seats  = int(t["seats"])
        result = tables_col.insert_one({
            "number": t["number"], "seats": seats,
            "status": "ready", "order_id": None, "created": now()
        })
        ready_queues_col.insert_one({
            "table_id": str(result.inserted_id),
            "table_number": t["number"], "seats": seats, "enqueued": now()
        })

    log("SETUP", f"Initialized {len(tables)} tables")
    return jsonify({"ok": True, "msg": f"Setup complete — {len(tables)} tables initialized"})

# ═══════════════════════════════════════════════════════════════════════════════
# TABLES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/tables")
def api_tables():
    return jsonify([s(t) for t in tables_col.find().limit(100)])

@app.route("/api/stats")
def api_stats():
    return jsonify({
        "total":    tables_col.count_documents({}),
        "ready":    tables_col.count_documents({"status": "ready"}),
        "occupied": tables_col.count_documents({"status": "occupied"}),
        "cleaning": tables_col.count_documents({"status": "cleaning"}),
        "waiting":  priority_col.count_documents({}),
        "active_orders": orders_col.count_documents({"status": "active"}),
        "total_orders":  orders_col.count_documents({})
    })

# ═══════════════════════════════════════════════════════════════════════════════
# READY QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/ready-queue")
def api_ready_queue():
    result = {}
    for item in ready_queues_col.find().sort("enqueued", 1).limit(50):
        k = str(item["seats"])
        result.setdefault(k, []).append({
            "qid": str(item["_id"]),
            "table_id": item["table_id"],
            "table_number": item["table_number"],
            "seats": item["seats"],
            "enqueued": item["enqueued"]
        })
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════════
# CLEANING QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/cleaning-queue")
def api_cleaning_queue():
    result = {}
    for item in clean_queues_col.find().sort("enqueued", 1).limit(50):
        k = str(item["seats"])
        result.setdefault(k, []).append({
            "qid": str(item["_id"]),
            "table_id": item["table_id"],
            "table_number": item["table_number"],
            "seats": item["seats"],
            "enqueued": item["enqueued"]
        })
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════════
# PRIORITY QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/priority-queue")
def api_priority_queue():
    items = list(priority_col.find().sort([("priority", 1), ("enqueued", 1)]).limit(100))
    return jsonify([{
        "qid": str(i["_id"]),
        "name": i["name"], "seats": i["seats"],
        "is_vip": i["is_vip"], "priority": i["priority"],
        "enqueued": i["enqueued"]
    } for i in items])

# ═══════════════════════════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/orders")
def api_orders():
    orders = list(orders_col.find().sort("created", -1).limit(200))
    for o in orders:
        o = s(o)
        if o.get("table_id"):
            t = tables_col.find_one({"_id": ObjectId(o["table_id"])})
            if t:
                o["table_number"] = t["table_number"] if "table_number" in t else t.get("number","?")
                o["table_seats"]  = t["seats"]
    return jsonify(orders)

@app.route("/api/orders/active")
def api_active_orders():
    orders = list(orders_col.find({"status": "active"}).sort("created", -1).limit(50))
    for o in orders:
        o = s(o)
        if o.get("table_id"):
            t = tables_col.find_one({"_id": ObjectId(o["table_id"])})
            if t:
                o["table_number"] = t.get("number","?")
                o["table_seats"]  = t["seats"]
    return jsonify(orders)

# ═══════════════════════════════════════════════════════════════════════════════
# NEW ORDER — allocate table
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/orders/new", methods=["POST"])
def api_new_order():
    d      = request.json
    name   = d.get("name", "Guest").strip()
    seats  = int(d.get("seats", 2))
    is_vip = bool(d.get("is_vip", False))

    if not name:
        return jsonify({"ok": False, "msg": "Customer name required"}), 400

    priority = 0 if is_vip else PRIORITY_MAP.get(seats, 6)

    # Try to dequeue from ready queue
    rq = ready_queues_col.find_one({"seats": seats}, sort=[("enqueued", 1)])
    if rq:
        tid = rq["table_id"]
        ready_queues_col.delete_one({"_id": rq["_id"]})

        res = orders_col.insert_one({
            "name": name, "seats": seats, "is_vip": is_vip,
            "priority": priority, "table_id": tid,
            "status": "active", "created": now(), "paid_at": None
        })
        oid = str(res.inserted_id)

        tables_col.update_one(
            {"_id": ObjectId(tid)},
            {"$set": {"status": "occupied", "order_id": oid}}
        )
        t = tables_col.find_one({"_id": ObjectId(tid)})
        log("ALLOCATED", f"Table {t.get('number')} ({seats} seats) → {name} (VIP={is_vip})")
        return jsonify({
            "ok": True, "allocated": True, "order_id": oid,
            "table": t.get("number"), "seats": seats,
            "msg": f"Table {t.get('number')} allocated to {name}"
        })
    else:
        # No table available — add to priority queue
        priority_col.insert_one({
            "name": name, "seats": seats, "is_vip": is_vip,
            "priority": priority, "enqueued": now()
        })
        log("QUEUED", f"{name} (seats={seats}, VIP={is_vip}) → priority queue (P{priority})")
        return jsonify({
            "ok": True, "allocated": False,
            "msg": f"No {seats}-seat table available. {name} added to priority queue"
        })

# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENT — moves table to cleaning queue
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/orders/<oid>/pay", methods=["POST"])
def api_pay(oid):
    order = orders_col.find_one({"_id": ObjectId(oid)})
    if not order:
        return jsonify({"ok": False, "msg": "Order not found"}), 404

    tid   = order["table_id"]
    table = tables_col.find_one({"_id": ObjectId(tid)})

    orders_col.update_one(
        {"_id": ObjectId(oid)},
        {"$set": {"status": "paid", "paid_at": now()}}
    )
    tables_col.update_one(
        {"_id": ObjectId(tid)},
        {"$set": {"status": "cleaning", "order_id": None}}
    )
    clean_queues_col.insert_one({
        "table_id": tid,
        "table_number": table.get("number","?"),
        "seats": table["seats"],
        "enqueued": now()
    })

    log("PAYMENT", f"Table {table.get('number')} paid → cleaning queue")
    return jsonify({"ok": True, "msg": f"Payment done. Table {table.get('number')} sent to cleaning queue"})

# ═══════════════════════════════════════════════════════════════════════════════
# MARK CLEANED — returns to ready queue or serves priority customer
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/cleaning/<qid>/cleaned", methods=["POST"])
def api_cleaned(qid):
    cq = clean_queues_col.find_one({"_id": ObjectId(qid)})
    if not cq:
        return jsonify({"ok": False, "msg": "Not found"}), 404

    tid   = cq["table_id"]
    seats = cq["seats"]
    table = tables_col.find_one({"_id": ObjectId(tid)})
    clean_queues_col.delete_one({"_id": ObjectId(qid)})

    # Check priority queue: exact seat match first, then VIP any seat
    pq = priority_col.find_one({"seats": seats}, sort=[("priority", 1), ("enqueued", 1)])
    if not pq:
        pq = priority_col.find_one({"is_vip": True}, sort=[("enqueued", 1)])

    if pq:
        priority_col.delete_one({"_id": pq["_id"]})
        res = orders_col.insert_one({
            "name": pq["name"], "seats": pq["seats"], "is_vip": pq["is_vip"],
            "priority": pq["priority"], "table_id": tid,
            "status": "active", "created": now(), "paid_at": None
        })
        oid = str(res.inserted_id)
        tables_col.update_one(
            {"_id": ObjectId(tid)},
            {"$set": {"status": "occupied", "order_id": oid}}
        )
        log("CLEANED→ALLOCATED", f"Table {table.get('number')} cleaned → allocated to {pq['name']} from priority queue")
        return jsonify({"ok": True, "msg": f"Table {table.get('number')} cleaned & allocated to {pq['name']} from queue"})
    else:
        ready_queues_col.insert_one({
            "table_id": tid, "table_number": table.get("number","?"),
            "seats": seats, "enqueued": now()
        })
        tables_col.update_one(
            {"_id": ObjectId(tid)},
            {"$set": {"status": "ready", "order_id": None}}
        )
        log("CLEANED→READY", f"Table {table.get('number')} cleaned → ready queue")
        return jsonify({"ok": True, "msg": f"Table {table.get('number')} cleaned and returned to ready queue"})

# ═══════════════════════════════════════════════════════════════════════════════
# LOGS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/logs")
def api_logs():
    entries = list(logs_col.find().sort("ts", -1).limit(100))
    return jsonify([{"action": e["action"], "detail": e["detail"], "ts": e["ts"]} for e in entries])

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def page_dashboard():  return render_template("dashboard.html")

@app.route("/setup")
def page_setup():      return render_template("setup.html")

@app.route("/orders")
def page_orders():     return render_template("orders.html")

@app.route("/cleaning")
def page_cleaning():   return render_template("cleaning.html")

@app.route("/queues")
def page_queues():     return render_template("queues.html")

@app.route("/history")
def page_history():    return render_template("history.html")

@app.route("/logs")
def page_logs():       return render_template("logs.html")

if __name__ == "__main__":
    app.run(debug=False, port=5000)
