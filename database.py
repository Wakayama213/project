import sqlite3
from datetime import datetime, timedelta
from config import DB_PATH, SUBSCRIPTION_DAYS


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            paid_until TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            status TEXT,
            created_at TEXT,
            confirmed_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (user_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, datetime.now().isoformat()),
        )
        conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "user_id": row[0],
        "username": row[1],
        "first_name": row[2],
        "paid_until": row[3],
        "created_at": row[4],
    }


def is_subscribed(user_id):
    user = get_user(user_id)
    if not user or not user["paid_until"]:
        return False
    return datetime.fromisoformat(user["paid_until"]) > datetime.now()


def extend_subscription(user_id):
    user = get_user(user_id)
    now = datetime.now()
    if user and user["paid_until"]:
        current = datetime.fromisoformat(user["paid_until"])
        start = max(current, now)
    else:
        start = now
    new_until = start + timedelta(days=SUBSCRIPTION_DAYS)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET paid_until = ? WHERE user_id = ?",
        (new_until.isoformat(), user_id),
    )
    conn.commit()
    conn.close()
    return new_until


def create_payment(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (user_id, status, created_at) VALUES (?, ?, ?)",
        (user_id, "pending", datetime.now().isoformat()),
    )
    payment_id = cur.lastrowid
    conn.commit()
    conn.close()
    return payment_id


def confirm_payment(payment_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE payments SET status = ?, confirmed_at = ? WHERE id = ?",
        ("confirmed", datetime.now().isoformat(), payment_id),
    )
    conn.commit()
    conn.close()


def get_active_subscribers():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE paid_until IS NOT NULL")
    rows = cur.fetchall()
    conn.close()
    result = []
    for row in rows:
        if is_subscribed(row[0]):
            result.append(row[0])
    return result