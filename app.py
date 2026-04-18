from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import pytz
import os
import hashlib
import secrets
import string
from functools import wraps
from dotenv import load_dotenv

IST = pytz.timezone("Asia/Kolkata")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client    = MongoClient(MONGO_URI)
db        = client["cafequeue_db"]

tables_col       = db["tables"]
ready_queues_col = db["ready_queues"]
clean_queues_col = db["cleaning_queues"]
priority_col     = db["priority_queue"]
orders_col       = db["orders"]
logs_col         = db["logs"]
users_col        = db["users"]

# ── Indexes ───────────────────────────────────────────────────────────────────
def ensure_indexes():
    tables_col.create_index([("branch_id", 1), ("status", 1), ("number", 1)], background=True)
    tables_col.create_index([("branch_id", 1), ("order_id", 1)], background=True)
    ready_queues_col.create_index([("branch_id", 1), ("seats", 1), ("enqueued", 1)], background=True)
    # Unique index on table_id prevents duplicate ready-queue entries
    try:
        ready_queues_col.create_index("table_id", unique=True, background=True)
    except Exception:
        pass  # index already exists
    clean_queues_col.create_index([("branch_id", 1), ("seats", 1), ("enqueued", 1)], background=True)
    priority_col.create_index([("branch_id", 1), ("priority", 1), ("enqueued", 1)], background=True)
    orders_col.create_index([("branch_id", 1), ("status", 1), ("created", -1)], background=True)
    logs_col.create_index([("branch_id", 1), ("ts", -1)], background=True)
    # Clean up null-username docs from old schema, then rebuild index safely
    users_col.delete_many({"username": None})
    users_col.delete_many({"username": {"$exists": False}})
    try:
        users_col.drop_index("username_1")
    except Exception:
        pass
    users_col.create_index("username", unique=True, sparse=True, background=True)
    users_col.create_index("branch_id", background=True)

ensure_indexes()


def repair_ready_queue(branch):
    """
    Safely rebuild ready_queues for one branch using tables as source of truth.
    - Removes any entries whose table is NOT in 'ready' status (occupied/cleaning/missing)
    - Removes duplicate entries for the same table_id (keeps only one per table)
    - Does NOT touch orders, logs, users, or any other collection.
    """
    # Gather all table_ids that are truly ready for this branch
    ready_tables = {
        str(t["_id"]): t
        for t in tables_col.find({"branch_id": branch, "status": "ready"})
    }

    # Remove every ready-queue entry whose table is not in ready state
    # (occupied, cleaning, or deleted table)
    non_ready_ids = []
    seen_table_ids = set()
    for rq in ready_queues_col.find({"branch_id": branch}):
        tid = rq.get("table_id")
        if tid not in ready_tables:
            # Table is not ready → remove this entry
            non_ready_ids.append(rq["_id"])
        elif tid in seen_table_ids:
            # Duplicate for same table → remove extra
            non_ready_ids.append(rq["_id"])
        else:
            seen_table_ids.add(tid)

    if non_ready_ids:
        from bson import ObjectId as ObjId
        ready_queues_col.delete_many({"_id": {"$in": non_ready_ids}})

    # Upsert one entry per truly-ready table that has no queue entry yet
    for tid, table in ready_tables.items():
        if tid not in seen_table_ids:
            ready_queues_col.update_one(
                {"table_id": tid},
                {"$set": {
                    "branch_id":    branch,
                    "table_id":     tid,
                    "table_number": table.get("number", "?"),
                    "seats":        table["seats"],
                    "enqueued":     datetime.now(IST).isoformat()
                }},
                upsert=True
            )


PRIORITY_MAP = { "vip": 0, 10: 1, 8: 2, 6: 3, 4: 4, 2: 5 }

# ── Helpers ───────────────────────────────────────────────────────────────────
def s(doc):
    if not doc: return None
    doc["_id"] = str(doc["_id"])
    return doc

def now():
    return datetime.now(IST).isoformat()

def log(action, detail=""):
    logs_col.insert_one({"branch_id": session.get("branch_id","system"),
                         "action": action, "detail": detail, "ts": now()})

def bid():
    return session.get("branch_id")

def generate_branch_id():
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "CAFE-" + "".join(secrets.choice(chars) for _ in range(4))
        if not users_col.find_one({"branch_id": code}):
            return code

def hash_password(password):
    salt = secrets.token_hex(16)
    return salt, hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password, salt, hashed):
    return hashlib.sha256((salt + password).encode()).hexdigest() == hashed

# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "msg": "Not authenticated"}), 401
            flash("Please sign in to continue.", "error")
            return redirect(url_for("page_login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "msg": "Not authenticated"}), 401
            flash("Please sign in to continue.", "error")
            return redirect(url_for("page_login"))
        if session.get("role") != "admin":
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "msg": "Admin access required"}), 403
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/register", methods=["GET", "POST"])
def page_register():
    if session.get("user_id"):
        return redirect(url_for("page_dashboard"))

    if request.method == "POST":
        full_name        = request.form.get("full_name", "").strip()
        username         = request.form.get("username", "").strip().lower()
        password         = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role             = request.form.get("role", "staff")
        branch_input     = request.form.get("branch_id", "").strip().upper()

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        if not all(c.isalnum() or c == "_" for c in username):
            flash("Username may only contain letters, numbers, and underscores.", "error")
            return render_template("register.html")
        if role not in ("admin", "staff"):
            role = "staff"
        if users_col.find_one({"username": username}):
            flash("That username is already taken.", "error")
            return render_template("register.html")

        if role == "admin":
            branch_id = generate_branch_id()
        else:
            if not branch_input:
                flash("Staff members must enter their admin's Branch ID.", "error")
                return render_template("register.html")
            admin_user = users_col.find_one({"branch_id": branch_input, "role": "admin"})
            if not admin_user:
                flash(f"No admin found with Branch ID '{branch_input}'. Please check and try again.", "error")
                return render_template("register.html")
            branch_id = branch_input

        salt, hashed = hash_password(password)
        users_col.insert_one({
            "username": username, "full_name": full_name or username,
            "salt": salt, "password": hashed,
            "role": role, "branch_id": branch_id, "created": now()
        })
        logs_col.insert_one({
            "branch_id": branch_id, "action": "USER_CREATED",
            "detail": f"New {role} account: '{username}' ({full_name})", "ts": now()
        })

        if role == "admin":
            flash(f"Account created! Your Branch ID is: {branch_id} — share this with your staff so they can join.", "ok")
        else:
            flash("Account created! You can now sign in.", "ok")
        return redirect(url_for("page_login"))

    return render_template("register.html")

# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/login", methods=["GET", "POST"])
def page_login():
    if session.get("user_id"):
        return redirect(url_for("page_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = users_col.find_one({"username": username})
        if user and verify_password(password, user["salt"], user["password"]):
            session.clear()
            session["user_id"]   = str(user["_id"])
            session["username"]  = user["username"]
            session["full_name"] = user.get("full_name", user["username"])
            session["role"]      = user.get("role", "staff")
            session["branch_id"] = user["branch_id"]
            logs_col.insert_one({
                "branch_id": user["branch_id"], "action": "LOGIN",
                "detail": f"User '{username}' signed in ({user['role']})", "ts": now()
            })
            return redirect(url_for("page_dashboard"))
        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def page_logout():
    username = session.get("username", "unknown")
    branch   = session.get("branch_id", "system")
    logs_col.insert_one({"branch_id": branch, "action": "LOGOUT",
                          "detail": f"User '{username}' signed out", "ts": now()})
    session.clear()
    flash("You have been signed out.", "ok")
    return redirect(url_for("page_login"))

# ═══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT (admin, branch-scoped)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/users")
@admin_required
def api_users():
    users = list(users_col.find({"branch_id": bid()}, {"password": 0, "salt": 0}).sort("created", 1))
    return jsonify([s(u) for u in users])

@app.route("/api/users/new", methods=["POST"])
@admin_required
def api_users_new():
    d = request.json
    username = d.get("username", "").strip().lower()
    password = d.get("password", "")
    full_name = d.get("full_name", "").strip()
    role = d.get("role", "staff")
    if not username or not password:
        return jsonify({"ok": False, "msg": "Username and password required"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "msg": "Password must be at least 6 characters"}), 400
    if users_col.find_one({"username": username}):
        return jsonify({"ok": False, "msg": f"Username '{username}' already exists"}), 409
    salt, hashed = hash_password(password)
    users_col.insert_one({"username": username, "full_name": full_name or username,
                           "salt": salt, "password": hashed,
                           "role": role if role in ("staff","admin") else "staff",
                           "branch_id": bid(), "created": now()})
    log("USER_CREATED", f"Admin added {role} account: '{username}'")
    return jsonify({"ok": True, "msg": f"User '{username}' added to your branch"})

@app.route("/api/users/<uid>/delete", methods=["POST"])
@admin_required
def api_users_delete(uid):
    if uid == session.get("user_id"):
        return jsonify({"ok": False, "msg": "Cannot delete your own account"}), 400
    user = users_col.find_one({"_id": ObjectId(uid), "branch_id": bid()})
    if not user:
        return jsonify({"ok": False, "msg": "User not found in your branch"}), 404
    users_col.delete_one({"_id": ObjectId(uid)})
    log("USER_DELETED", f"Removed account: '{user['username']}'")
    return jsonify({"ok": True, "msg": f"User '{user['username']}' removed"})

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP (admin, branch-scoped)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/setup", methods=["POST"])
@admin_required
def api_setup():
    data = request.json
    tables = data.get("tables", [])
    if not tables:
        return jsonify({"ok": False, "msg": "No tables provided"}), 400
    branch = bid()
    for col in [tables_col, ready_queues_col, clean_queues_col, priority_col, orders_col]:
        col.delete_many({"branch_id": branch})
    for t in tables:
        seats = int(t["seats"])
        result = tables_col.insert_one({
            "branch_id": branch, "number": t["number"], "seats": seats,
            "status": "ready", "order_id": None, "created": now()
        })
        _tid = str(result.inserted_id)
        ready_queues_col.update_one(
            {"table_id": _tid},
            {"$set": {
                "branch_id": branch, "table_id": _tid,
                "table_number": t["number"], "seats": seats, "enqueued": now()
            }},
            upsert=True
        )
    log("SETUP", f"Initialized {len(tables)} tables")
    return jsonify({"ok": True, "msg": f"Setup complete — {len(tables)} tables initialized"})

# ═══════════════════════════════════════════════════════════════════════════════
# TABLES & STATS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/tables")
@login_required
def api_tables():
    return jsonify([s(t) for t in tables_col.find({"branch_id": bid()}).limit(100)])

@app.route("/api/stats")
@login_required
def api_stats():
    branch = bid()
    return jsonify({
        "total":         tables_col.count_documents({"branch_id": branch}),
        "ready":         tables_col.count_documents({"branch_id": branch, "status": "ready"}),
        "occupied":      tables_col.count_documents({"branch_id": branch, "status": "occupied"}),
        "cleaning":      tables_col.count_documents({"branch_id": branch, "status": "cleaning"}),
        "waiting":       priority_col.count_documents({"branch_id": branch}),
        "active_orders": orders_col.count_documents({"branch_id": branch, "status": "active", "table_id": {"$ne": None}}),
        "total_orders":  orders_col.count_documents({"branch_id": branch}),
        "branch_id":     branch,
    })

# ═══════════════════════════════════════════════════════════════════════════════
# QUEUES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/ready-queue")
@login_required
def api_ready_queue():
    result = {}
    for item in ready_queues_col.find({"branch_id": bid()}).sort("enqueued", 1).limit(50):
        k = str(item["seats"])
        result.setdefault(k, []).append({
            "qid": str(item["_id"]), "table_id": item["table_id"],
            "table_number": item["table_number"], "seats": item["seats"], "enqueued": item["enqueued"]
        })
    return jsonify(result)

@app.route("/api/cleaning-queue")
@login_required
def api_cleaning_queue():
    result = {}
    for item in clean_queues_col.find({"branch_id": bid()}).sort("enqueued", 1).limit(50):
        k = str(item["seats"])
        result.setdefault(k, []).append({
            "qid": str(item["_id"]), "table_id": item["table_id"],
            "table_number": item["table_number"], "seats": item["seats"], "enqueued": item["enqueued"]
        })
    return jsonify(result)

@app.route("/api/priority-queue")
@login_required
def api_priority_queue():
    items = list(priority_col.find({"branch_id": bid()}).sort([("priority", 1), ("enqueued", 1)]).limit(100))
    return jsonify([{
        "qid": str(i["_id"]), "name": i["name"], "seats": i["seats"],
        "is_vip": i["is_vip"], "priority": i["priority"], "enqueued": i["enqueued"]
    } for i in items])

# ═══════════════════════════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════════════════════════
def _attach_table(o):
    if o.get("table_id"):
        t = tables_col.find_one({"_id": ObjectId(o["table_id"]), "branch_id": bid()})
        if t:
            o["table_number"] = t.get("number", "?")
            o["table_seats"]  = t["seats"]
    return o

@app.route("/api/orders")
@login_required
def api_orders():
    orders = list(orders_col.find({"branch_id": bid()}).sort("created", -1).limit(200))
    return jsonify([_attach_table(s(o)) for o in orders])

@app.route("/api/orders/active")
@login_required
def api_active_orders():
    orders = list(orders_col.find({"branch_id": bid(), "status": "active"}).sort("created", -1).limit(50))
    return jsonify([_attach_table(s(o)) for o in orders])

@app.route("/api/orders/new", methods=["POST"])
@login_required
def api_new_order():
    d = request.json
    name   = d.get("name", "Guest").strip()
    seats  = int(d.get("seats", 2))
    is_vip = bool(d.get("is_vip", False))
    branch = bid()
    if not name:
        return jsonify({"ok": False, "msg": "Customer name required"}), 400
    priority = 0 if is_vip else PRIORITY_MAP.get(seats, 6)
    rq = ready_queues_col.find_one({"branch_id": branch, "seats": seats}, sort=[("enqueued", 1)])
    if rq:
        tid = rq["table_id"]
        ready_queues_col.delete_one({"_id": rq["_id"]})
        res = orders_col.insert_one({
            "branch_id": branch, "name": name, "seats": seats, "is_vip": is_vip,
            "priority": priority, "table_id": tid,
            "status": "active", "created": now(), "paid_at": None
        })
        oid = str(res.inserted_id)
        tables_col.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "occupied", "order_id": oid}})
        t = tables_col.find_one({"_id": ObjectId(tid)})
        log("ALLOCATED", f"Table {t.get('number')} ({seats}s) → {name} (VIP={is_vip})")
        return jsonify({"ok": True, "allocated": True, "order_id": oid,
                        "table": t.get("number"), "seats": seats,
                        "msg": f"Table {t.get('number')} allocated to {name}"})
    else:
        priority_col.insert_one({"branch_id": branch, "name": name, "seats": seats,
                                  "is_vip": is_vip, "priority": priority, "enqueued": now()})
        log("QUEUED", f"{name} (seats={seats}, VIP={is_vip}) → P{priority}")
        return jsonify({"ok": True, "allocated": False,
                        "msg": f"No {seats}-seat table available. {name} added to priority queue"})

@app.route("/api/orders/<oid>/pay", methods=["POST"])
@login_required
def api_pay(oid):
    branch = bid()
    order  = orders_col.find_one({"_id": ObjectId(oid), "branch_id": branch})
    if not order:
        return jsonify({"ok": False, "msg": "Order not found"}), 404
    tid   = order["table_id"]
    table = tables_col.find_one({"_id": ObjectId(tid)})
    orders_col.update_one({"_id": ObjectId(oid)}, {"$set": {"status": "paid", "paid_at": now()}})
    tables_col.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "cleaning", "order_id": None}})
    clean_queues_col.insert_one({
        "branch_id": branch, "table_id": tid,
        "table_number": table.get("number","?"), "seats": table["seats"], "enqueued": now()
    })
    log("PAYMENT", f"Table {table.get('number')} paid → cleaning queue")
    return jsonify({"ok": True, "msg": f"Payment done. Table {table.get('number')} sent to cleaning queue"})

@app.route("/api/cleaning/<qid>/cleaned", methods=["POST"])
@login_required
def api_cleaned(qid):
    branch = bid()
    cq = clean_queues_col.find_one({"_id": ObjectId(qid), "branch_id": branch})
    if not cq:
        return jsonify({"ok": False, "msg": "Not found"}), 404
    tid   = cq["table_id"]
    seats = cq["seats"]
    table = tables_col.find_one({"_id": ObjectId(tid)})
    clean_queues_col.delete_one({"_id": ObjectId(qid)})
    pq = priority_col.find_one({"branch_id": branch, "seats": seats}, sort=[("priority", 1), ("enqueued", 1)])
    if not pq:
        pq = priority_col.find_one({"branch_id": branch, "is_vip": True}, sort=[("enqueued", 1)])
    if pq:
        priority_col.delete_one({"_id": pq["_id"]})
        res = orders_col.insert_one({
            "branch_id": branch, "name": pq["name"], "seats": pq["seats"],
            "is_vip": pq["is_vip"], "priority": pq["priority"], "table_id": tid,
            "status": "active", "created": now(), "paid_at": None
        })
        tables_col.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "occupied", "order_id": str(res.inserted_id)}})
        log("CLEANED→ALLOCATED", f"Table {table.get('number')} → {pq['name']} from priority queue")
        return jsonify({"ok": True, "msg": f"Table {table.get('number')} cleaned & allocated to {pq['name']}"})
    else:
        ready_queues_col.update_one(
            {"table_id": tid},
            {"$set": {
                "branch_id": branch, "table_id": tid,
                "table_number": table.get("number", "?"), "seats": seats, "enqueued": now()
            }},
            upsert=True
        )
        tables_col.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "ready", "order_id": None}})
        log("CLEANED→READY", f"Table {table.get('number')} cleaned → ready queue")
        return jsonify({"ok": True, "msg": f"Table {table.get('number')} cleaned and returned to ready queue"})

@app.route("/api/logs")
@login_required
def api_logs():
    entries = list(logs_col.find({"branch_id": bid()}).sort("ts", -1).limit(100))
    return jsonify([{"action": e["action"], "detail": e["detail"], "ts": e["ts"]} for e in entries])

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
@login_required
def page_dashboard():  return render_template("dashboard.html")

@app.route("/setup")
@admin_required
def page_setup():      return render_template("setup.html")

@app.route("/orders")
@login_required
def page_orders():     return render_template("orders.html")

@app.route("/cleaning")
@login_required
def page_cleaning():   return render_template("cleaning.html")

@app.route("/queues")
@login_required
def page_queues():     return render_template("queues.html")

@app.route("/history")
@login_required
def page_history():    return render_template("history.html")

@app.route("/logs")
@admin_required
def page_logs():       return render_template("logs.html")

@app.route("/users")
@admin_required
def page_users():      return render_template("users.html")

@app.route("/simulation")
@admin_required
def page_simulation(): return render_template("simulation.html")


# ═══════════════════════════════════════════════════════════════════════════════
# MONTE CARLO SIMULATION API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/simulation/run", methods=["POST"])
@admin_required
def api_run_simulation():
    import random
    import math

    d               = request.json
    branch          = bid()
    num_simulations = int(d.get("num_simulations", 1000))
    sim_hours       = float(d.get("sim_hours", 8))
    cleaning_min    = 10.0
    date_str        = d.get("date", "")  # optional YYYY-MM-DD filter

    # Build date-scoped query if date provided
    date_query = {"branch_id": branch}
    if date_str:
        try:
            day_start = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0))
            day_end   = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
            date_query["created"] = {"$gte": day_start.isoformat(), "$lte": day_end.isoformat()}
        except Exception:
            date_str = ""

    # ── Compute arrival_rate from real order timestamps (date-scoped) ─────────
    all_orders = list(orders_col.find(date_query, {"created": 1}).sort("created", 1))

    arrival_rate = 1.0   # default fallback
    if len(all_orders) >= 2:
        try:
            t_first = datetime.fromisoformat(all_orders[0]["created"]).astimezone(IST)
            t_last  = datetime.fromisoformat(all_orders[-1]["created"]).astimezone(IST)
            total_hours = (t_last - t_first).total_seconds() / 3600
            if total_hours >= 0.5:
                arrival_rate = len(all_orders) / total_hours
        except Exception:
            pass

    avg_dining_min = 45.0
    dining_std_min = 15.0

    # Pull real table config from DB for this branch
    tables = list(tables_col.find({"branch_id": branch}, {"seats": 1, "number": 1}))
    if not tables:
        return jsonify({"ok": False, "msg": "No tables configured. Please run Setup first."}), 400

    seat_counts = {}
    for t in tables:
        s = t["seats"]
        seat_counts[s] = seat_counts.get(s, 0) + 1
    total_tables = len(tables)

    # Dining durations — scoped to selected date if provided
    paid_query = {**date_query, "status": "paid", "paid_at": {"$ne": None}}
    paid_orders = list(orders_col.find(paid_query, {"created": 1, "paid_at": 1, "seats": 1}).limit(200))

    real_durations = []
    for o in paid_orders:
        try:
            t1 = datetime.fromisoformat(o["created"]).astimezone(IST)
            t2 = datetime.fromisoformat(o["paid_at"]).astimezone(IST)
            mins = (t2 - t1).total_seconds() / 60
            if 5 < mins < 300:
                real_durations.append(mins)
        except Exception:
            pass

    if len(real_durations) >= 10:
        avg_dining_min = sum(real_durations) / len(real_durations)
        variance = sum((x - avg_dining_min)**2 for x in real_durations) / len(real_durations)
        dining_std_min = math.sqrt(variance)
        data_source = "historical"
    else:
        data_source = "simulated"

    # ── Monte Carlo core ──────────────────────────────────────────────────────
    sim_minutes = sim_hours * 60
    results = {
        "wait_times":        [],
        "queue_lengths":     [],
        "throughput":        [],
        "occupancy_rates":   [],
        "customers_turned":  [],
        "peak_queue_sizes":  [],
    }

    for _ in range(num_simulations):
        # Each simulation: model one full operating day
        table_free_at = [0.0] * total_tables   # minute when each table becomes free
        current_time  = 0.0
        wait_times_run    = []
        queue_length_snapshots = []
        served = 0
        turned_away = 0
        peak_queue = 0

        # Generate all arrivals via Poisson process
        arrivals = []
        t = 0.0
        lam = arrival_rate / 60.0  # per minute
        while t < sim_minutes:
            gap = random.expovariate(lam)
            t  += gap
            if t < sim_minutes:
                # Random party size weighted realistically
                party = random.choices(
                    [2, 4, 6, 8, 10],
                    weights=[30, 35, 20, 10, 5]
                )[0]
                arrivals.append((t, party))

        for arrival_time, party_size in arrivals:
            # Find best available table (exact size, then next bigger)
            best_table = None
            best_free_at = float("inf")
            for idx, free_at in enumerate(table_free_at):
                table_seats = tables[idx]["seats"]
                if table_seats >= party_size:
                    if free_at <= arrival_time:
                        # Table already free — no wait
                        if best_table is None or table_seats < tables[best_table]["seats"]:
                            best_table = idx
                            best_free_at = free_at
                    else:
                        # Table busy — shortest wait
                        if free_at < best_free_at and table_seats >= party_size:
                            best_table = idx
                            best_free_at = free_at

            if best_table is None:
                turned_away += 1
                continue

            wait = max(0.0, table_free_at[best_table] - arrival_time)
            wait_times_run.append(wait)

            # Dining duration — normal distribution clipped to [10, 180] min
            dining = max(10, min(180, random.gauss(avg_dining_min, dining_std_min)))
            cleaning = max(5, random.gauss(cleaning_min, 3))

            table_free_at[best_table] = arrival_time + wait + dining + cleaning
            served += 1

            # Queue snapshot — count tables still occupied at this arrival time
            busy = sum(1 for f in table_free_at if f > arrival_time)
            queue_length_snapshots.append(busy)
            if busy > peak_queue:
                peak_queue = busy

        total_arrivals = len(arrivals)
        results["wait_times"].append(
            sum(wait_times_run) / len(wait_times_run) if wait_times_run else 0
        )
        results["queue_lengths"].append(
            sum(queue_length_snapshots) / len(queue_length_snapshots) if queue_length_snapshots else 0
        )
        results["throughput"].append(served)
        results["occupancy_rates"].append(
            (served / total_arrivals * 100) if total_arrivals > 0 else 0
        )
        results["customers_turned"].append(turned_away)
        results["peak_queue_sizes"].append(peak_queue)

    def stats(arr):
        if not arr: return {}
        arr_s = sorted(arr)
        n = len(arr_s)
        mean = sum(arr_s) / n
        variance = sum((x - mean)**2 for x in arr_s) / n
        return {
            "mean":   round(mean, 2),
            "min":    round(arr_s[0], 2),
            "max":    round(arr_s[-1], 2),
            "std":    round(math.sqrt(variance), 2),
            "p25":    round(arr_s[int(n * 0.25)], 2),
            "p50":    round(arr_s[int(n * 0.50)], 2),
            "p75":    round(arr_s[int(n * 0.75)], 2),
            "p95":    round(arr_s[int(n * 0.95)], 2),
            "histogram": _histogram(arr_s, 10),
        }

    def _histogram(arr, bins):
        if not arr: return []
        lo, hi = arr[0], arr[-1]
        if lo == hi: return [{"label": str(round(lo, 1)), "count": len(arr)}]
        width = (hi - lo) / bins
        buckets = [0] * bins
        for v in arr:
            idx = min(int((v - lo) / width), bins - 1)
            buckets[idx] += 1
        return [{"label": round(lo + i * width, 1), "count": buckets[i]} for i in range(bins)]

    # Table recommendation
    avg_turned = stats(results["customers_turned"])["mean"]
    recommendation = ""
    if avg_turned > len(arrivals) * 0.15:
        recommendation = f"⚠️ On average {avg_turned:.0f} customers per day cannot be seated. Consider adding more tables."
    elif stats(results["wait_times"])["p95"] > 20:
        recommendation = f"⏳ 95th percentile wait time is {stats(results['wait_times'])['p95']:.1f} min. Peak hours may need extra staff or faster cleaning."
    else:
        recommendation = f"✅ Your current table configuration handles demand well. Average wait: {stats(results['wait_times'])['mean']:.1f} min."

    return jsonify({
        "ok": True,
        "num_simulations": num_simulations,
        "sim_hours":        sim_hours,
        "arrival_rate":     arrival_rate,
        "avg_dining_min":   round(avg_dining_min, 1),
        "dining_std_min":   round(dining_std_min, 1),
        "data_source":      data_source,
        "total_tables":     total_tables,
        "seat_breakdown":   seat_counts,
        "historical_orders": len(real_durations),
        "stats": {
            "wait_time":       stats(results["wait_times"]),
            "queue_length":    stats(results["queue_lengths"]),
            "throughput":      stats(results["throughput"]),
            "occupancy":       stats(results["occupancy_rates"]),
            "turned_away":     stats(results["customers_turned"]),
            "peak_queue":      stats(results["peak_queue_sizes"]),
        },
        "recommendation": recommendation,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
def _get_slot(hour):
    if 6  <= hour < 11: return "morning"
    if 11 <= hour < 15: return "lunch"
    if 15 <= hour < 18: return "evening"
    if 18 <= hour < 23: return "dinner"
    return None

@app.route("/api/analytics/daily")
@login_required
def api_analytics_daily():
    branch    = bid()
    date_str  = request.args.get("date", "")  # YYYY-MM-DD or empty = all dates
    query     = {"branch_id": branch}

    if date_str:
        try:
            day_start = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0))
            day_end   = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
            query["created"] = {"$gte": day_start.isoformat(), "$lte": day_end.isoformat()}
        except Exception:
            pass

    orders = list(orders_col.find(query, {"created": 1}).sort("created", 1))

    day_map = {}
    for o in orders:
        try:
            dt = datetime.fromisoformat(o["created"]).astimezone(IST)
        except Exception:
            continue
        ds   = dt.strftime("%Y-%m-%d")
        hour = dt.hour
        slot = _get_slot(hour)
        if ds not in day_map:
            day_map[ds] = {"total": 0, "slots": {"morning": 0, "lunch": 0, "evening": 0, "dinner": 0}}
        day_map[ds]["total"] += 1
        if slot:
            day_map[ds]["slots"][slot] += 1

    result = []
    for ds in sorted(day_map.keys()):
        d    = day_map[ds]
        peak = max(d["slots"], key=lambda k: d["slots"][k])
        result.append({"date": ds, "customers": d["total"], "peak": peak, "slots": d["slots"]})
    return jsonify(result)


@app.route("/api/analytics/timeslots")
@login_required
def api_analytics_timeslots():
    branch   = bid()
    date_str = request.args.get("date", "")
    query    = {"branch_id": branch}

    if date_str:
        try:
            day_start = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0))
            day_end   = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
            query["created"] = {"$gte": day_start.isoformat(), "$lte": day_end.isoformat()}
        except Exception:
            pass

    orders = list(orders_col.find(query, {"created": 1, "seats": 1}))

    slots = {
        "morning": {"customers": 0, "total_seats": 0},
        "lunch":   {"customers": 0, "total_seats": 0},
        "evening": {"customers": 0, "total_seats": 0},
        "dinner":  {"customers": 0, "total_seats": 0},
    }
    for o in orders:
        try:
            dt   = datetime.fromisoformat(o["created"]).astimezone(IST)
            slot = _get_slot(dt.hour)
            if not slot:
                continue
            slots[slot]["customers"]   += 1
            slots[slot]["total_seats"] += int(o.get("seats", 0))
        except Exception:
            continue

    result = {}
    for slot, data in slots.items():
        c = data["customers"]
        result[slot] = {"customers": c, "avg_seats": round(data["total_seats"] / c, 1) if c > 0 else 0}
    return jsonify(result)


@app.route("/api/analytics/timeline")
@login_required
def api_analytics_timeline():
    branch   = bid()
    date_str = request.args.get("date", "")
    query    = {"branch_id": branch}

    if date_str:
        try:
            day_start = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0))
            day_end   = IST.localize(datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
            query["created"] = {"$gte": day_start.isoformat(), "$lte": day_end.isoformat()}
        except Exception:
            pass

    orders = list(orders_col.find(query, {"created": 1}).sort("created", 1))
    bucket_map = {}
    for o in orders:
        try:
            dt = datetime.fromisoformat(o["created"]).astimezone(IST)
        except Exception:
            continue
        bucket_min = (dt.minute // 30) * 30
        bucket_key = dt.strftime(f"%H:{bucket_min:02d}")
        bucket_map[bucket_key] = bucket_map.get(bucket_key, 0) + 1
    result = [{"time": k, "customers": v} for k, v in sorted(bucket_map.items())]
    return jsonify(result)


@app.route("/api/analytics/dates")
@login_required
def api_analytics_dates():
    """Return sorted list of all dates that have order data for this branch."""
    branch = bid()
    orders = list(orders_col.find({"branch_id": branch}, {"created": 1}))
    date_set = set()
    for o in orders:
        try:
            dt = datetime.fromisoformat(o["created"]).astimezone(IST)
            date_set.add(dt.strftime("%Y-%m-%d"))
        except Exception:
            continue
    return jsonify(sorted(date_set))


@app.route("/analytics")
@login_required
def page_analytics(): return render_template("analytics.html")


# ═══════════════════════════════════════════════════════════════════════════════
# QUEUE REPAIR (admin-safe, no data loss)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/queue/repair", methods=["POST"])
@admin_required
def api_repair_queue():
    branch = bid()
    repair_ready_queue(branch)
    ready_count = ready_queues_col.count_documents({"branch_id": branch})
    log("QUEUE_REPAIR", f"Ready queue rebuilt. {ready_count} entries now.")
    return jsonify({"ok": True, "msg": f"Ready queue repaired. {ready_count} entries.", "ready": ready_count})


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/users/update-profile", methods=["POST"])
@login_required
def api_update_profile():
    d         = request.json or {}
    uid       = session.get("user_id")
    full_name = d.get("full_name", "").strip()
    username  = d.get("username", "").strip().lower()
    password  = d.get("password", "").strip()

    if not username:
        return jsonify({"ok": False, "msg": "Username cannot be empty"}), 400
    if not all(c.isalnum() or c == "_" for c in username):
        return jsonify({"ok": False, "msg": "Username may only contain letters, numbers, underscores"}), 400
    if password and len(password) < 6:
        return jsonify({"ok": False, "msg": "Password must be at least 6 characters"}), 400

    # Check username uniqueness (exclude current user)
    existing = users_col.find_one({"username": username, "_id": {"$ne": ObjectId(uid)}})
    if existing:
        return jsonify({"ok": False, "msg": f"Username '{username}' is already taken"}), 409

    updates = {}
    if full_name:
        updates["full_name"] = full_name
    if username:
        updates["username"] = username
    if password:
        salt, hashed     = hash_password(password)
        updates["salt"]     = salt
        updates["password"] = hashed

    if not updates:
        return jsonify({"ok": False, "msg": "No changes provided"}), 400

    users_col.update_one({"_id": ObjectId(uid)}, {"$set": updates})

    # Keep session in sync
    if "username" in updates:
        session["username"] = updates["username"]
    if "full_name" in updates:
        session["full_name"] = updates["full_name"]

    log("PROFILE_UPDATE", f"User '{session['username']}' updated their profile")
    return jsonify({"ok": True, "msg": "Profile updated successfully"})


@app.route("/profile")
@login_required
def page_profile(): return render_template("profile.html")

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
@app.errorhandler(403)
def error_403(e):
    return render_template("error.html",
        code=403,
        title="Access Denied",
        message="You don't have permission to view this page. This area is restricted to admins only.",
        icon="🔒"
    ), 403

@app.errorhandler(404)
def error_404(e):
    return render_template("error.html",
        code=404,
        title="Page Not Found",
        message="The page you're looking for doesn't exist or has been moved.",
        icon="🔍"
    ), 404

@app.errorhandler(500)
def error_500(e):
    return render_template("error.html",
        code=500,
        title="Server Error",
        message="Something went wrong on our end. Please try again or contact your administrator.",
        icon="⚠️"
    ), 500


if __name__ == "__main__":
    # ── Startup banner ────────────────────────────────────────────────────────
    print("\n" + "─" * 48)
    print("  ☕  CaféQueue — starting up")
    print("─" * 48)
    try:
        client.admin.command("ping")
        print("  ✅  MongoDB connected       mongodb://localhost:27017")
    except Exception as e:
        print(f"  ❌  MongoDB connection FAILED: {e}")
    db_name = db.name
    col_count = len(db.list_collection_names())
    print(f"  ✅  Database ready          {db_name}  ({col_count} collections)")
    print(f"  ✅  Auth                    session-based, SHA-256 passwords")
    print(f"  ✅  Timezone                 Asia/Kolkata (IST)")
    print(f"  ✅  Multi-tenant            branch_id isolation enabled")
    print("─" * 48)
    print("  🌐  Running at  →  http://localhost:5000")
    print("─" * 48 + "\n")
    app.run(debug=False, port=5000)