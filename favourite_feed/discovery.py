# Seller discovery works in small saved steps so the browser can stop and resume a search.
import json
from requests.exceptions import HTTPError
from datetime import datetime, timezone
from config import SEARCH_TERMS, MIN_SHOP_RATING, MIN_SHOP_REVIEWS, MIN_SHOP_AGE_DAYS, TARGET_SHIPPING_COUNTRIES
from favourite_feed.database import connect_database, PROJECT_ROOT
from favourite_feed.etsy_api import etsy_get
from favourite_feed.shop_management import add_shop
from favourite_feed.seller_filters import classify_wysiwyg, is_loose_cabochon, EVIDENCE_RANK

# Create the settings, review list, recently checked cache, candidate queue and search progress tables.
def setup(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_settings (id INTEGER PRIMARY KEY, terms TEXT NOT NULL)")
    conn.execute("""CREATE TABLE IF NOT EXISTS discovery_shops (
        shop_id INTEGER PRIMARY KEY, name TEXT, rating REAL, reviews INTEGER,
        country TEXT, evidence TEXT, listing_id INTEGER, status TEXT NOT NULL DEFAULT 'pending')""")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_checked (shop_id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_queue (shop_id INTEGER PRIMARY KEY, evidence TEXT, listing_id INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_run (id INTEGER PRIMARY KEY, terms TEXT, position INTEGER, status TEXT)")
    conn.execute("INSERT OR IGNORE INTO discovery_settings VALUES (1,?)",(json.dumps(SEARCH_TERMS),))

# Turn one search phrase per line into a unique list, preserving the original order.
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

# Save a snapshot of the current search terms and reset the search position and candidate queue.
def start():
    with connect_database() as conn:
        setup(conn)
        terms=conn.execute("SELECT terms FROM discovery_settings WHERE id=1").fetchone()[0]
        conn.execute("DELETE FROM discovery_queue")
        conn.execute("INSERT OR REPLACE INTO discovery_run VALUES (1,?,0,'running')",(terms,))

# Perform one unit of work: check a queued seller or fetch one page of search results.
def step():
    with connect_database() as conn:
        setup(conn)
        run=conn.execute("SELECT * FROM discovery_run WHERE id=1").fetchone()
        if not run or run["status"]!="running":
            return "Not running"
        terms=json.loads(run["terms"])
        pos=run["position"]
        queued=conn.execute("SELECT * FROM discovery_queue ORDER BY shop_id LIMIT 1").fetchone()
    # Check queued sellers first, so each candidate can be assessed before fetching more listings.
    if queued:
        sid=queued["shop_id"]
        try:
            shop=etsy_get(f"shops/{sid}")
        except HTTPError as exc:
            if exc.response is None or exc.response.status_code not in (404, 410):
                raise
            # A missing shop should not block the queue. Retry in a future search
            # after the ordinary checked-shop cache expires.
            with connect_database() as conn:
                conn.execute("INSERT OR REPLACE INTO discovery_checked VALUES (?,datetime('now'))",(sid,))
                conn.execute("DELETE FROM discovery_queue WHERE shop_id=?",(sid,))
            return f"Skipped unavailable shop {sid}"
        # Read seller statistics; missing ratings and review counts are treated as zero.
        rating=shop.get("review_average") or 0
        reviews=shop.get("review_count") or 0
        country=shop.get("shipping_from_country_iso")
        age=(datetime.now(timezone.utc).timestamp()-(shop.get("create_date") or datetime.now(timezone.utc).timestamp()))/86400
        _, excluded_names=legacy_exclusions()
        # Apply the configured rating, review, age and country rules. Unknown shipping countries remain eligible for manual review.
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
    # Each search term has three pages of up to 100 listings; stop once all pages and queued shops are processed.
    if pos>=len(terms)*3:
        with connect_database() as conn:
            conn.execute("UPDATE discovery_run SET status='complete' WHERE id=1")
        return "Search complete"
    historical_ids,_=legacy_exclusions()
    # Integer division selects the search term; the remainder selects its page offset.
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
            # Keep existing review decisions, but improve the evidence for shops still awaiting review.
            existing=conn.execute("SELECT evidence,status FROM discovery_shops WHERE shop_id=?",(sid,)).fetchone()
            if existing:
                if existing["status"]=="pending" and EVIDENCE_RANK.get(evidence,0)>EVIDENCE_RANK.get(existing["evidence"],0):
                    conn.execute("UPDATE discovery_shops SET evidence=?,listing_id=? WHERE shop_id=?",(evidence,listing_id,sid))
                continue
            # Avoid rediscovering historical sellers or those checked in the last 30 days.
            if sid in historical_ids:
                continue
            if conn.execute("SELECT 1 FROM discovery_checked WHERE shop_id=? AND checked_at>=datetime('now','-30 days')",(sid,)).fetchone():
                continue
            conn.execute("""INSERT OR IGNORE INTO discovery_queue
                SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM monitored_shops WHERE shop_id=?)""",
                (sid,evidence,listing_id,sid))
            # If several listings point to the same seller, retain the strongest evidence and its example listing.
            old=conn.execute("SELECT evidence FROM discovery_queue WHERE shop_id=?",(sid,)).fetchone()
            if old and EVIDENCE_RANK.get(evidence,0)>EVIDENCE_RANK.get(old["evidence"],0):
                conn.execute("UPDATE discovery_queue SET evidence=?,listing_id=? WHERE shop_id=?",(evidence,listing_id,sid))
        conn.execute("UPDATE discovery_run SET position=position+1 WHERE id=1")
    return "Searched "+term

# Apply a manual review decision; favourites are added to monitoring before their review status changes.
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
