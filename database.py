"""
database.py – SQLite database layer
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "subscriptions.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        full_name   TEXT,
        joined_at   TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS plans (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        category    TEXT NOT NULL,
        duration    INTEGER NOT NULL,
        price       REAL NOT NULL,
        description TEXT,
        services    TEXT,
        is_active   INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS orders (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id        TEXT UNIQUE NOT NULL,
        user_id         INTEGER NOT NULL,
        plan_id         INTEGER NOT NULL,
        amount          REAL NOT NULL,
        status          TEXT DEFAULT 'pending',
        payment_method  TEXT,
        upi_txn_id      TEXT,
        screenshot_file TEXT,
        created_at      TEXT DEFAULT (datetime('now')),
        approved_at     TEXT,
        approved_by     INTEGER,
        notes           TEXT
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        plan_id     INTEGER NOT NULL,
        order_id    TEXT NOT NULL,
        bot_name    TEXT DEFAULT '',
        started_at  TEXT NOT NULL,
        expires_at  TEXT NOT NULL,
        is_active   INTEGER DEFAULT 1
    );
    """)

    # Migrate: add bot_name column if it doesn't exist yet (safe for existing DBs)
    try:
        c.execute("ALTER TABLE subscriptions ADD COLUMN bot_name TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # Column already exists

    c.execute("SELECT COUNT(*) FROM plans")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO plans (name,category,duration,price,description,services,is_active) VALUES (?,?,?,?,?,?,?)",
            [
                ("BasicBot",       "Bot Hosting Subscription", 30, 199.0, "Basic bot hosting", "autoleech", 1),
                ("MasterTGxfb2al", "Bot Hosting Subscription", 30, 350.0, "Master plan with FB & autoleech", "fb,fb,autoleech", 1),
                ("ProBot",         "Bot Hosting Subscription", 60, 599.0, "Pro plan all features", "fb,autoleech,premium", 1),
            ]
        )

    conn.commit()
    conn.close()


# ── Users ──────────────────────────────────────────────────────

def upsert_user(user_id, username, full_name):
    conn = get_conn()
    conn.execute(
        """INSERT INTO users (user_id,username,full_name) VALUES (?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name""",
        (user_id, username, full_name)
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Plans ───────────────────────────────────────────────────────

def get_plans(active_only=True):
    conn = get_conn()
    q = "SELECT * FROM plans" + (" WHERE is_active=1" if active_only else "") + " ORDER BY price"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plan(plan_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_plan(name, category, duration, price, description, services):
    conn = get_conn()
    conn.execute(
        "INSERT INTO plans (name,category,duration,price,description,services) VALUES (?,?,?,?,?,?)",
        (name, category, duration, price, description, services)
    )
    conn.commit()
    conn.close()


def toggle_plan(plan_id):
    conn = get_conn()
    conn.execute("UPDATE plans SET is_active = 1 - is_active WHERE id=?", (plan_id,))
    conn.commit()
    conn.close()


def delete_plan(plan_id):
    conn = get_conn()
    conn.execute("DELETE FROM plans WHERE id=?", (plan_id,))
    conn.commit()
    conn.close()


# ── Orders ──────────────────────────────────────────────────────

def create_order(order_id, user_id, plan_id, amount):
    conn = get_conn()
    conn.execute(
        "INSERT INTO orders (order_id,user_id,plan_id,amount) VALUES (?,?,?,?)",
        (order_id, user_id, plan_id, amount)
    )
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_order_payment(order_id, method, screenshot=None, txn_id=None):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET payment_method=?, screenshot_file=?, upi_txn_id=? WHERE order_id=?",
        (method, screenshot, txn_id, order_id)
    )
    conn.commit()
    conn.close()


def approve_order(order_id, admin_id):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET status='approved', approved_at=datetime('now'), approved_by=? WHERE order_id=?",
        (admin_id, order_id)
    )
    conn.commit()
    conn.close()


def reject_order(order_id, admin_id, notes=""):
    conn = get_conn()
    conn.execute(
        "UPDATE orders SET status='rejected', approved_by=?, notes=? WHERE order_id=?",
        (admin_id, notes, order_id)
    )
    conn.commit()
    conn.close()


def get_pending_orders():
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.*, u.username, u.full_name, p.name as plan_name
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        JOIN plans p ON o.plan_id = p.id
        WHERE o.status = 'pending'
        ORDER BY o.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_orders(limit=None):
    conn = get_conn()
    q = """
        SELECT o.*, u.username, u.full_name, p.name as plan_name
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        JOIN plans p ON o.plan_id = p.id
        ORDER BY o.created_at DESC
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_orders(user_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.*, p.name as plan_name FROM orders o
           JOIN plans p ON o.plan_id=p.id
           WHERE o.user_id=? ORDER BY o.created_at DESC LIMIT 7""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Subscriptions ────────────────────────────────────────────────

def activate_subscription(user_id, plan_id, order_id, duration_days, bot_name=""):
    now = datetime.utcnow()
    expires = now + timedelta(days=duration_days)
    conn = get_conn()
    conn.execute(
        "UPDATE subscriptions SET is_active=0 WHERE user_id=? AND plan_id=?",
        (user_id, plan_id)
    )
    conn.execute(
        "INSERT INTO subscriptions (user_id,plan_id,order_id,bot_name,started_at,expires_at) VALUES (?,?,?,?,?,?)",
        (user_id, plan_id, order_id, bot_name, now.isoformat(), expires.isoformat())
    )
    conn.commit()
    conn.close()
    return expires


def get_user_subscriptions(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.*, p.name as plan_name, p.category, p.services, p.duration
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.user_id = ? AND s.is_active = 1
        ORDER BY s.expires_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_subscriptions(active_only=False):
    conn = get_conn()
    q = """
        SELECT s.*, u.username, u.full_name, p.name as plan_name, p.price
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
        JOIN plans p ON s.plan_id = p.id
    """
    if active_only:
        q += " WHERE s.is_active=1"
    q += " ORDER BY s.expires_at DESC"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_expiring_soon(hours=48):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.*, u.user_id, u.username, p.name as plan_name, p.id as plan_id
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
        JOIN plans p ON s.plan_id = p.id
        WHERE s.is_active = 1
          AND datetime(s.expires_at) <= datetime('now', ? || ' hours')
          AND datetime(s.expires_at) > datetime('now')
    """, (str(hours),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def expire_subscriptions():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.user_id, p.name as plan_name, p.id as plan_id
        FROM subscriptions s JOIN plans p ON s.plan_id=p.id
        WHERE s.is_active=1 AND datetime(s.expires_at) <= datetime('now')
    """).fetchall()
    conn.execute(
        "UPDATE subscriptions SET is_active=0 WHERE is_active=1 AND datetime(expires_at) <= datetime('now')"
    )
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


# ── Stats ────────────────────────────────────────────────────────

def get_stats():
    conn = get_conn()
    stats = {
        "total_users":  conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "total_orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "pending":      conn.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0],
        "approved":     conn.execute("SELECT COUNT(*) FROM orders WHERE status='approved'").fetchone()[0],
        "rejected":     conn.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'").fetchone()[0],
        "revenue":      conn.execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='approved'").fetchone()[0],
        "active_subs":  conn.execute("SELECT COUNT(*) FROM subscriptions WHERE is_active=1").fetchone()[0],
    }
    conn.close()
    return stats
    
