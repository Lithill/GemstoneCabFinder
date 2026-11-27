"""Gemstone quiz and reference library routes."""
import json
import hashlib
import secrets
from functools import lru_cache
from flask import render_template, request, abort, redirect, url_for, jsonify
from favourite_feed.database import connect_database
from favourite_feed.gemstone_quiz import GEMS, canonical_name, clean_label, material_info, display_answer, material_category, visual_alternatives, identify as identify_quiz_gem, options as quiz_options
from favourite_feed.gemstone_identification_tips import TIPS as GEMSTONE_TIPS

@lru_cache(maxsize=8)
def _quiz_order(seed, ids):
    return tuple(sorted(ids, key=lambda i: hashlib.sha256(
        f"{seed}:{i}".encode("ascii")).digest()))


def gemstone_quiz():
    """Photo-first, read-only identification practice using collected Etsy images."""
    try:
        position = max(0, int(request.args.get("position", "0")))
    except (TypeError, ValueError):
        position = 0
    seed = request.args.get("seed", "")
    if not (len(seed) == 16 and all(c in "0123456789abcdef" for c in seed)):
        seed = secrets.token_hex(8)
    with connect_database() as conn:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listing_images_listing_rank ON listing_images(listing_id, image_rank)")
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_labels (listing_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        # Repair saved labels once per changed value; uncertain fragments go back to review.
        saved_labels = conn.execute("SELECT q.listing_id, q.name, l.title FROM quiz_labels q JOIN listings l ON l.listing_id=q.listing_id").fetchall()
        labels = {}
        repairs = []
        unresolved = []
        for listing_id, name, title in saved_labels:
            cleaned = clean_label(name, title)
            if cleaned is None:
                unresolved.append((listing_id, name))
                continue
            labels[listing_id] = cleaned
            if cleaned != name:
                repairs.append((cleaned, listing_id, name))
        if repairs or unresolved:
            conn.execute("CREATE TABLE IF NOT EXISTS quiz_label_cleanup_backup (listing_id INTEGER, name TEXT, PRIMARY KEY(listing_id, name))")
            conn.executemany("INSERT OR IGNORE INTO quiz_label_cleanup_backup VALUES (?, ?)", [(i, old) for _, i, old in repairs] + unresolved)
            conn.executemany("UPDATE quiz_labels SET name=? WHERE listing_id=? AND name=?", repairs)
            conn.executemany("DELETE FROM quiz_labels WHERE listing_id=? AND name=?", unresolved)
        custom = {name for name in labels.values() if name}
        rows = conn.execute("""
            SELECT l.listing_id, l.title, l.listing_url,
                   (SELECT image_url FROM listing_images i
                    WHERE i.listing_id = l.listing_id
                    AND i.image_url IS NOT NULL AND i.image_url != '' ORDER BY image_rank LIMIT 1) AS photo
            FROM listings l
            WHERE l.seen_at IS NOT NULL AND EXISTS (SELECT 1 FROM listing_images i
                          WHERE i.listing_id = l.listing_id
                            AND i.image_url IS NOT NULL AND i.image_url != '')
            ORDER BY l.published_at DESC, l.listing_id DESC
        """).fetchall()
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_learning (name TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, confident INTEGER NOT NULL DEFAULT 0, needs INTEGER NOT NULL DEFAULT 0)")
        learning = {row[0]: (row[1], row[2], row[3]) for row in conn.execute("SELECT name, attempts, confident, needs FROM quiz_learning")}
    # Only quiz titles with one recognised gemstone; do not guess from photos.
    custom = tuple(sorted(custom))
    eligible = [(row, labels[row["listing_id"]] if row["listing_id"] in labels else identify_quiz_gem(row["title"], custom)) for row in rows]
    review = [row for row, gem in eligible if not gem and row["listing_id"] not in labels]
    rows = [(row, gem) for row, gem in eligible if gem]
    # A fresh random order per quiz, stable while navigating Previous/Next.
    order = _quiz_order(seed, tuple(row["listing_id"] for row, _ in rows))
    by_id = {row["listing_id"]: (row, gem) for row, gem in rows}
    rows = [by_id[i] for i in order]
    available = {gem for _, gem in rows}
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        saved = conn.execute("SELECT value FROM quiz_settings WHERE id=1").fetchone()
    known = set(GEMS) | set(custom)
    prior = json.loads(saved[0]) if saved else {}
    if isinstance(prior, list):
        # Migrate the original 30-name allowlist without disabling new names.
        original = set(list(GEMS)[:30])
        excluded = original - set(prior)
    else:
        excluded = {canonical_name(name) for name in prior.get("excluded", [])}
    enabled = known - excluded
    rows = [(row, gem) for row, gem in rows if gem in enabled]
    mode = request.args.get("mode", "all")
    if mode in {"natural", "organic", "manufactured", "uncertain"}:
        rows = [(row, gem) for row, gem in rows if material_category(gem) == mode]
    elif mode == "practice":
        rows = [(row, gem) for row, gem in rows if learning.get(gem, (0, 0, 0))[2] > learning.get(gem, (0, 0, 0))[1]]
    elif mode == "adaptive":
        # Keep ordering stable during a session; prioritize weak material on a fresh round.
        rows = _adaptive_rows(seed, rows, learning)
    total = len(rows)
    position = min(position, max(0, total - 1))
    item, answer = rows[position] if total else (None, None)
    followup = request.args.get("practice", "")
    example = next(((row, gem) for row, gem in rows if gem == followup), None)
    if example:
        item, answer = example
    practice_notice = bool(followup and not example)
    choices = quiz_options(answer, seed, item["listing_id"], available & enabled) if item else []
    return render_template("gemstone_quiz.html",
                           item=item, answer=answer, material=material_info(answer), display_answer=display_answer, recognition_tip=GEMSTONE_TIPS.get(answer, ""),
                           choices=choices, tips=GEMSTONE_TIPS, mode=mode, learning=learning.get(answer, (0, 0, 0)),
                           position=position, total=total, seed=seed,
                           gem_names=sorted(available), enabled=enabled, available=available,
                           review=review[:10] if request.args.get('review') == '1' else [], review_count=len(review),
                           review_open=request.args.get('review') == '1',
                           practice=bool(example), practice_notice=practice_notice)


# Bounded session ordering cache; ratings affect the next fresh round.
_adaptive_orders = {}
def _adaptive_rows(seed, rows, learning):
    key = (seed, tuple(row["listing_id"] for row, _ in rows))
    order = _adaptive_orders.get(key)
    if order is None:
        ranked = sorted(rows, key=lambda pair: learning.get(pair[1], (0, 0, 0))[1] - learning.get(pair[1], (0, 0, 0))[2])
        order = tuple(row["listing_id"] for row, _ in ranked)
        if len(_adaptive_orders) >= 8:
            _adaptive_orders.clear()
        _adaptive_orders[key] = order
    by_id = {row["listing_id"]: (row, gem) for row, gem in rows}
    return [by_id[i] for i in order]


def gemstone_quiz_learning():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    rating = data.get("rating")
    if not isinstance(name, str) or not name or len(name) > 100 or not isinstance(rating, str) or rating not in {"knew", "guess", "practice"}:
        abort(400)
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_learning (name TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, confident INTEGER NOT NULL DEFAULT 0, needs INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO quiz_learning(name) VALUES (?)", (name,))
        conn.execute("UPDATE quiz_learning SET attempts=attempts+1, confident=confident+?, needs=needs+? WHERE name=?", (int(rating == "knew"), int(rating != "knew"), name))
    return jsonify(ok=True)


def gemstone_quiz_questionable(listing_id):
    name = " ".join(request.form.get("name", "").split())
    if len(name) > 100:
        abort(400)
    with connect_database() as conn:
        if not conn.execute("SELECT 1 FROM listings WHERE listing_id=? AND seen_at IS NOT NULL", (listing_id,)).fetchone():
            abort(404)
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_labels (listing_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO quiz_labels VALUES (?, ?)", (listing_id, canonical_name(name) if name else ""))
    return redirect(url_for("gemstone_quiz"))


def gemstone_library():
    query = request.args.get("q", "").strip().casefold()
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_labels (listing_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        labels = dict(conn.execute("SELECT listing_id, name FROM quiz_labels"))
        rows = conn.execute("""SELECT l.listing_id, l.title, (SELECT image_url FROM listing_images i WHERE i.listing_id=l.listing_id AND i.image_url IS NOT NULL AND i.image_url != '' ORDER BY image_rank LIMIT 1) FROM listings l WHERE l.seen_at IS NOT NULL ORDER BY l.published_at DESC""").fetchall()
    custom = tuple(sorted({name for name in labels.values() if name}))
    photos = {}
    for listing_id, title, photo in rows:
        if photo:
            name = labels.get(listing_id) if listing_id in labels else identify_quiz_gem(title, custom)
            if name:
                photos.setdefault(name, photo)
    names = sorted(set(GEMS) | set(custom))
    entries = [(name, material_info(name), photos.get(name), GEMSTONE_TIPS.get(name, ""), list(dict.fromkeys(GEMS.get(name, ([], []))[1] + visual_alternatives(name)))[:5]) for name in names if not query or query in (name + " " + display_answer(name)).casefold()]
    return render_template("gemstone_library.html", entries=entries, query=query, display_answer=display_answer)


def gemstone_quiz_settings():
    displayed = set(request.form.getlist("displayed"))
    selected = set(request.form.getlist("gem"))
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        saved = conn.execute("SELECT value FROM quiz_settings WHERE id=1").fetchone()
        prior = json.loads(saved[0]) if saved else {}
        excluded = (set(list(GEMS)[:30]) - set(prior)) if isinstance(prior, list) else {canonical_name(name) for name in prior.get("excluded", [])}
        excluded = (excluded - displayed) | (displayed - selected)
        conn.execute("INSERT OR REPLACE INTO quiz_settings VALUES (1, ?)", (json.dumps({"excluded": sorted(excluded)}),))
    return redirect(url_for("gemstone_quiz"))


def gemstone_quiz_labels():
    ids = request.form.getlist("listing_id")
    if len(ids) > 10 or len(set(ids)) != len(ids) or any(not i.isascii() or not i.isdigit() or len(i) > 18 for i in ids):
        abort(400)
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_labels (listing_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        existing = {gem.casefold(): gem for gem in GEMS}
        existing.update({row[0].casefold(): row[0] for row in conn.execute("SELECT DISTINCT name FROM quiz_labels WHERE name != ''")})
        updates = []
        for raw in ids:
            listing_id = int(raw)
            name = " ".join(request.form.get("name_" + raw, "").split())
            skip = request.form.get("skip_" + raw) == "1"
            if len(name) > 100:
                abort(400)
            if not name and not skip:
                continue
            if not conn.execute("SELECT 1 FROM listings WHERE listing_id=? AND seen_at IS NOT NULL", (listing_id,)).fetchone():
                abort(404)
            name = "" if skip else canonical_name(existing.setdefault(name.casefold(), name[:1].upper() + name[1:]))
            updates.append((listing_id, name))
        conn.executemany("INSERT OR REPLACE INTO quiz_labels VALUES (?, ?)", updates)
    return redirect(url_for("gemstone_quiz", review=1) + "#review")


def gemstone_quiz_label(listing_id):
    name = " ".join(request.form.get("name", "").split())
    if len(name) > 100:
        abort(400)
    with connect_database() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS quiz_labels (listing_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        if not conn.execute("SELECT 1 FROM listings WHERE listing_id=? AND seen_at IS NOT NULL", (listing_id,)).fetchone():
            abort(404)
        existing = list(GEMS) + [r[0] for r in conn.execute("SELECT DISTINCT name FROM quiz_labels WHERE name != ''")]
        name = next((gem for gem in existing if gem.casefold() == name.casefold()), name[:1].upper() + name[1:])
        if not name and request.form.get("skip") != "1":
            abort(400)
        conn.execute("INSERT OR REPLACE INTO quiz_labels VALUES (?, ?)", (listing_id, name))
    return redirect(url_for("gemstone_quiz") + "#review")



def register_quiz_routes(app):
    app.get("/gemstone-quiz")(gemstone_quiz)
    app.post("/gemstone-quiz/learning")(gemstone_quiz_learning)
    app.post("/gemstone-quiz/questionable/<int:listing_id>")(gemstone_quiz_questionable)
    app.get("/gemstone-library")(gemstone_library)
    app.post("/gemstone-quiz/settings")(gemstone_quiz_settings)
    app.post("/gemstone-quiz/labels")(gemstone_quiz_labels)
    app.post("/gemstone-quiz/label/<int:listing_id>")(gemstone_quiz_label)
