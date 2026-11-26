import json
from datetime import datetime, timezone
from config import SEARCH_TERMS, MIN_SHOP_RATING, MIN_SHOP_REVIEWS, MIN_SHOP_AGE_DAYS, TARGET_SHIPPING_COUNTRIES
from favourite_feed.database import connect_database
from favourite_feed.etsy_api import etsy_get
from favourite_feed.shop_management import add_shop
import re
from config import FINISHED_JEWELLERY_TERMS, WYSIWYG_POSITIVE_PHRASES, WYSIWYG_NEGATIVE_PHRASES

def classify_wysiwyg(title, description="", rare_find=False):
    """Classify evidence that the buyer receives the pictured stone."""
    text = (str(title) + " " + str(description)).casefold()

    for phrase in WYSIWYG_NEGATIVE_PHRASES:
        if phrase in text:
            return "Likely random selection"

    for phrase in WYSIWYG_POSITIVE_PHRASES:
        if phrase in text:
            return "Likely WYSIWYG"

    if rare_find:
        return "Possible WYSIWYG - Rare find"

    return "Needs checking"

def is_loose_cabochon(title):
    title = title.casefold()

    if "cabochon" not in title and "cabochons" not in title:
        return False

    # Phrases suggesting the listing sells loose stones
    loose_stone_phrases = [
        "loose",
        "flat back",
        "flatback",
        "calibrated",
        "for jewelry making",
        "for jewellery making",
        "jewelry supply",
        "jewellery supply",
        "gemstone lot",
        "cabochon lot",
    ]

    # Remove loose-stone phrases before checking jewellery terms.
    # This protects phrases such as "for ring making".
    if "for ring making" in title:
        title = title.replace("for ring making", "")

    if "for pendant making" in title:
        title = title.replace("for pendant making", "")

    # Check for clear evidence that the listing sells loose stones
    is_loose_stone = any(
        phrase in title for phrase in loose_stone_phrases
    )

    # Check whether the title mentions finished jewellery
    is_finished_jewellery = any(
        re.search(r"\b" + re.escape(term) + r"\b", title)
        for term in FINISHED_JEWELLERY_TERMS
    )

    # Keep listings clearly described as loose stones
    if is_loose_stone:
        return True

    # Exclude listings mentioning finished jewellery
    if is_finished_jewellery:
        return False

    return True



def setup(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_settings (id INTEGER PRIMARY KEY, terms TEXT NOT NULL)")
    conn.execute("""CREATE TABLE IF NOT EXISTS discovery_shops (
        shop_id INTEGER PRIMARY KEY, name TEXT, rating REAL, reviews INTEGER,
        country TEXT, evidence TEXT, listing_id INTEGER, status TEXT NOT NULL DEFAULT 'pending')""")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_queue (shop_id INTEGER PRIMARY KEY, evidence TEXT, listing_id INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS discovery_run (id INTEGER PRIMARY KEY, terms TEXT, position INTEGER, status TEXT)")
    conn.execute("INSERT OR IGNORE INTO discovery_settings VALUES (1,?)",(json.dumps(SEARCH_TERMS),))

def terms_from_text(value):
    terms=list(dict.fromkeys(s.strip() for s in value.splitlines() if s.strip()))
    if not 1<=len(terms)<=50 or any(len(s)>100 for s in terms):
        raise ValueError("Enter 1–50 search terms, each at most 100 characters.")
    return terms

def start():
    with connect_database() as conn:
        setup(conn)
        terms=conn.execute("SELECT terms FROM discovery_settings WHERE id=1").fetchone()[0]
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
        qualifies=rating>=MIN_SHOP_RATING and reviews>=MIN_SHOP_REVIEWS and age>=MIN_SHOP_AGE_DAYS and (not country or country in TARGET_SHIPPING_COUNTRIES)
        with connect_database() as conn:
            if qualifies:
                conn.execute("""INSERT OR IGNORE INTO discovery_shops
                    (shop_id,name,rating,reviews,country,evidence,listing_id)
                    SELECT ?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM monitored_shops WHERE shop_id=?)""",
                    (sid,shop["shop_name"],rating,reviews,country,queued["evidence"],queued["listing_id"],sid))
            conn.execute("DELETE FROM discovery_queue WHERE shop_id=?",(sid,))
        return "Checked "+shop["shop_name"]
    if pos>=len(terms)*3:
        with connect_database() as conn:
            conn.execute("UPDATE discovery_run SET status='complete' WHERE id=1")
        return "Search complete"
    term=terms[pos//3]
    data=etsy_get("listings/active",{"keywords":term,"limit":100,"offset":(pos%3)*100,"sort_on":"score","buyer_country":"GB"})
    with connect_database() as conn:
        for item in data["results"]:
            if not is_loose_cabochon(item.get("title") or ""):
                continue
            sid=item.get("shop_id")
            if not sid:
                continue
            conn.execute("""INSERT OR IGNORE INTO discovery_queue
                SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM monitored_shops WHERE shop_id=?)
                AND NOT EXISTS (SELECT 1 FROM discovery_shops WHERE shop_id=?)""",
                (sid,classify_wysiwyg(item.get("title") or "",item.get("description") or ""),item.get("listing_id"),sid,sid))
        conn.execute("UPDATE discovery_run SET position=position+1 WHERE id=1")
    return "Searched "+term

def review(sid, action):
    with connect_database() as conn:
        setup(conn)
        row=conn.execute("SELECT * FROM discovery_shops WHERE shop_id=? AND status='pending'",(sid,)).fetchone()
    if not row:
        raise ValueError("Shop is no longer awaiting review.")
    if action=="favourite":
        actual,_=add_shop(row["name"])
        if actual!=sid:
            raise ValueError("Shop identity changed.")
    elif action!="reject":
        raise ValueError("Unknown review action.")
    with connect_database() as conn:
        if action=="favourite":
            conn.execute("UPDATE monitored_shops SET is_active=1 WHERE shop_id=?",(sid,))
        conn.execute("UPDATE discovery_shops SET status=? WHERE shop_id=?",(action,sid))
