import json
from datetime import datetime, timezone
from config import SEARCH_TERMS, MIN_SHOP_RATING, MIN_SHOP_REVIEWS, MIN_SHOP_AGE_DAYS, TARGET_SHIPPING_COUNTRIES
from favourite_feed.database import connect_database, PROJECT_ROOT
from favourite_feed.etsy_api import etsy_get
from favourite_feed.shop_management import add_shop
from favourite_feed.seller_filters import classify_wysiwyg, is_loose_cabochon, EVIDENCE_RANK

def setup(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_settings (id INTEGER PRIMARY KEY, terms TEXT NOT NULL)")
    conn.execute("""CREATE TABLE IF NOT EXISTS discovery_shops (
        shop_id INTEGER PRIMARY KEY, name TEXT, rating REAL, reviews INTEGER,
        country TEXT, evidence TEXT, listing_id INTEGER, status TEXT NOT NULL DEFAULT 'pending')""")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_checked (shop_id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_queue (shop_id INTEGER PRIMARY KEY, evidence TEXT, listing_id INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_run (id INTEGER PRIMARY KEY, terms TEXT, position INTEGER, status TEXT)")
    conn.execute("INSERT OR IGNORE INTO discovery_settings VALUES (1,?)",(json.dumps(SEARCH_TERMS),))

def terms_from_text(value):
    terms=list(dict.fromkeys(s.strip() for s in value.splitlines() if s.strip()))
    if not 1<=len(terms)<=50 or any(len(s)>100 for s in terms):
        raise ValueError("Enter 1–50 search terms, each at most 100 characters.")
    return terms

def legacy_exclusions():
    # The old history includes pending spreadsheet rows, not just rejections.
    # Existing pending rows take precedence; import the spreadsheet first.
    def lines(filename):
        path=PROJECT_ROOT / "data" / filename
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")] if path.exists() else []
    return ({int(v) for v in lines("reviewed_shop_ids.txt") if v.isdecimal()},
            {v.casefold() for v in lines("favourited_shops.txt")})

def start():
    with connect_database() as conn:
        setup(conn)
        terms=conn.execute("SELECT terms FROM discovery_settings WHERE id=1").fetchone()[0]
        conn.execute("DELETE FROM discovery_queue")
        conn.execute("INSERT OR REPLACE INTO discovery_run VALUES (1,?,0,'running')",(terms,))

def step():
    with connect_database() as conn:
        setup(conn)
        run=conn.execute("SELECT * FROM discovery_run WHERE id=1").fetchone()
        if not run or run["status"]!="running":
            return "Not running"
        terms=json.loads(run["terms"])
        pos=run["position"]
        queued=conn.execute("SELECT * FROM discovery_queue ORDER BY shop_id LIMIT 1").fetchone()
    if queued:
        sid=queued["shop_id"]
        shop=etsy_get(f"shops/{sid}")
        rating=shop.get("review_average") or 0
        reviews=shop.get("review_count") or 0
        country=shop.get("shipping_from_country_iso")
        age=(datetime.now(timezone.utc).timestamp()-(shop.get("create_date") or datetime.now(timezone.utc).timestamp()))/86400
        _, excluded_names=legacy_exclusions()
        qualifies=shop["shop_name"].casefold() not in excluded_names and rating>=MIN_SHOP_RATING and reviews>=MIN_SHOP_REVIEWS and age>=MIN_SHOP_AGE_DAYS and (not country or country in TARGET_SHIPPING_COUNTRIES)
        with connect_database() as conn:
            if qualifies:
                conn.execute("""INSERT OR IGNORE INTO discovery_shops
                    (shop_id,name,rating,reviews,country,evidence,listing_id)
                    SELECT ?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM monitored_shops WHERE shop_id=?)""",
                    (sid,shop["shop_name"],rating,reviews,country,queued["evidence"],queued["listing_id"],sid))
            conn.execute("INSERT OR REPLACE INTO discovery_checked VALUES (?,datetime('now'))",(sid,))
            conn.execute("DELETE FROM discovery_queue WHERE shop_id=?",(sid,))
        return "Checked "+shop["shop_name"]
    if pos>=len(terms)*3:
        with connect_database() as conn:
            conn.execute("UPDATE discovery_run SET status='complete' WHERE id=1")
        return "Search complete"
    historical_ids,_=legacy_exclusions()
    term=terms[pos//3]
    data=etsy_get("listings/active",{"keywords":term,"limit":100,"offset":(pos%3)*100,"sort_on":"score","buyer_country":"GB"})
    with connect_database() as conn:
        for item in data["results"]:
            if not is_loose_cabochon(item.get("title") or ""):
                continue
            sid=item.get("shop_id")
            if not sid:
                continue
            evidence=classify_wysiwyg(item.get("title") or "",item.get("description") or "")
            listing_id=item.get("listing_id")
            existing=conn.execute("SELECT evidence,status FROM discovery_shops WHERE shop_id=?",(sid,)).fetchone()
            if existing:
                if existing["status"]=="pending" and EVIDENCE_RANK.get(evidence,0)>EVIDENCE_RANK.get(existing["evidence"],0):
                    conn.execute("UPDATE discovery_shops SET evidence=?,listing_id=? WHERE shop_id=?",(evidence,listing_id,sid))
                continue
            if sid in historical_ids:
                continue
            if conn.execute("SELECT 1 FROM discovery_checked WHERE shop_id=? AND checked_at>=datetime('now','-30 days')",(sid,)).fetchone():
                continue
            conn.execute("""INSERT OR IGNORE INTO discovery_queue
                SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM monitored_shops WHERE shop_id=?)""",
                (sid,evidence,listing_id,sid))
            old=conn.execute("SELECT evidence FROM discovery_queue WHERE shop_id=?",(sid,)).fetchone()
            if old and EVIDENCE_RANK.get(evidence,0)>EVIDENCE_RANK.get(old["evidence"],0):
                conn.execute("UPDATE discovery_queue SET evidence=?,listing_id=? WHERE shop_id=?",(evidence,listing_id,sid))
        conn.execute("UPDATE discovery_run SET position=position+1 WHERE id=1")
    return "Searched "+term

def review(sid, action):
    with connect_database() as conn:
        setup(conn)
        row=conn.execute("SELECT * FROM discovery_shops WHERE shop_id=? AND status='pending'",(sid,)).fetchone()
    if not row:
        raise ValueError("Shop is no longer awaiting review.")
    if action=="favourite":
        add_shop(row["name"], expected_id=sid)
    elif action!="reject":
        raise ValueError("Unknown review action.")
    with connect_database() as conn:
        if action=="favourite":
            conn.execute("UPDATE monitored_shops SET is_active=1 WHERE shop_id=?",(sid,))
        conn.execute("UPDATE discovery_shops SET status=? WHERE shop_id=?",(action,sid))
