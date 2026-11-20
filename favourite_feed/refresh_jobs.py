"""Resumable manual refresh. A browser request processes one shop at a time."""
import json
import sqlite3
from datetime import datetime, timezone
from favourite_feed.database import connect_database
from favourite_feed.refresh import refresh_shop

def now():
    return datetime.now(timezone.utc).isoformat()

def ensure(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS refresh_runs (
            run_id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
            finished_at TEXT, status TEXT NOT NULL,
            total INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0,
            new_listings INTEGER NOT NULL DEFAULT 0, baselines INTEGER NOT NULL DEFAULT 0,
            failures INTEGER NOT NULL DEFAULT 0, last_shop TEXT, error TEXT
        );
        CREATE TABLE IF NOT EXISTS refresh_run_shops (
            run_id INTEGER NOT NULL, position INTEGER NOT NULL, shop_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', message TEXT,
            new_listings INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(run_id, position)
        );
    """)

def snapshot():
    with connect_database() as conn:
        ensure(conn)
        row = conn.execute("SELECT * FROM refresh_runs ORDER BY run_id DESC LIMIT 1").fetchone()
        if not row:
            return {"status":"never","total":0,"done":0}
        data = dict(row)
        data["issues"] = [dict(r) for r in conn.execute(
            "SELECT s.shop_id, m.shop_name, s.message FROM refresh_run_shops s "
            "JOIN monitored_shops m ON m.shop_id=s.shop_id "
            "WHERE s.run_id=? AND s.status='failed' ORDER BY s.position", (row["run_id"],))]
        return data

def start():
    with connect_database() as conn:
        ensure(conn)
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT run_id FROM refresh_runs WHERE status IN ('running','paused') ORDER BY run_id DESC LIMIT 1").fetchone()
        if existing:
            conn.execute("UPDATE refresh_runs SET status='running' WHERE run_id=?", (existing["run_id"],))
            return snapshot_after(conn, existing["run_id"])
        shops = conn.execute("SELECT shop_id FROM monitored_shops WHERE is_active=1 ORDER BY shop_id").fetchall()
        cur = conn.execute("INSERT INTO refresh_runs(started_at,status,total) VALUES(?,'running',?)", (now(),len(shops)))
        run_id = cur.lastrowid
        conn.executemany("INSERT INTO refresh_run_shops(run_id,position,shop_id) VALUES(?,?,?)",
                         [(run_id,i,r["shop_id"]) for i,r in enumerate(shops)])
        if not shops:
            conn.execute("UPDATE refresh_runs SET status='completed', finished_at=? WHERE run_id=?", (now(),run_id))
        return snapshot_after(conn, run_id)

def snapshot_after(conn, run_id):
    return dict(conn.execute("SELECT * FROM refresh_runs WHERE run_id=?", (run_id,)).fetchone())

def pause():
    with connect_database() as conn:
        ensure(conn)
        conn.execute("UPDATE refresh_runs SET status='paused' WHERE status='running'")
    return snapshot()

def step():
    # A transaction claim prevents two tabs from processing the same shop.
    with connect_database() as conn:
        ensure(conn)
        conn.execute("BEGIN IMMEDIATE")
        run = conn.execute("SELECT * FROM refresh_runs WHERE status='running' ORDER BY run_id DESC LIMIT 1").fetchone()
        if not run:
            return snapshot()
        pending = conn.execute("SELECT * FROM refresh_run_shops WHERE run_id=? AND status='pending' ORDER BY position LIMIT 1", (run["run_id"],)).fetchone()
        if not pending:
            if not conn.execute("SELECT 1 FROM refresh_run_shops WHERE run_id=? AND status='working'", (run["run_id"],)).fetchone():
                conn.execute("UPDATE refresh_runs SET status='completed', finished_at=? WHERE run_id=?", (now(),run["run_id"]))
            return snapshot_after(conn,run["run_id"])
        conn.execute("UPDATE refresh_run_shops SET status='working' WHERE run_id=? AND position=?", (run["run_id"],pending["position"]))
        shop = conn.execute("SELECT * FROM monitored_shops WHERE shop_id=?", (pending["shop_id"],)).fetchone()
        before = conn.execute("SELECT COUNT(*) FROM listings WHERE shop_id=?", (pending["shop_id"],)).fetchone()[0]
    error = None
    try:
        message = refresh_shop(shop)
    except Exception as exc:
        error = str(exc)[:300]
        message = error
    with connect_database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        after = conn.execute("SELECT COUNT(*) FROM listings WHERE shop_id=?", (pending["shop_id"],)).fetchone()[0]
        count = max(0,after-before)
        conn.execute("UPDATE refresh_run_shops SET status=?,message=?,new_listings=? WHERE run_id=? AND position=?",
                     ("failed" if error else "done",message,count,run["run_id"],pending["position"]))
        rate_limited = bool(error and ("rate limit" in error.lower() or "429" in error))
        conn.execute("""UPDATE refresh_runs SET done=done+1, new_listings=new_listings+?,
            baselines=baselines+?, failures=failures+?,last_shop=?,
            status=CASE WHEN ? THEN 'paused' ELSE status END,
            error=CASE WHEN ? THEN ? ELSE error END WHERE run_id=?""",
            (count,int(not error and not shop["last_checked"]),int(bool(error)),
             shop["shop_name"],int(rate_limited),int(rate_limited),error,run["run_id"]))
        remaining = conn.execute("SELECT 1 FROM refresh_run_shops WHERE run_id=? AND status IN ('pending','working') LIMIT 1", (run["run_id"],)).fetchone()
        if not remaining:
            conn.execute("UPDATE refresh_runs SET status='completed',finished_at=? WHERE run_id=?", (now(),run["run_id"]))
        return snapshot_after(conn,run["run_id"])
