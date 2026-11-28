"""Separate houseplant diary; gemstone database remains untouched."""
from datetime import date, datetime, timezone, timedelta
from functools import wraps
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from collections import defaultdict
from statistics import mean
from urllib.parse import urlsplit

from flask import Blueprint, abort, redirect, render_template, request, url_for
from favourite_feed.plant_collection import INITIAL_CARE, INITIAL_PLANTS
from favourite_feed.plant_watering_guides import CHECK_INTERVALS

plants = Blueprint("plants", __name__)
# Keep plant records in a separate private SQLite file, not the gemstone database or encrypted health vault.
DB_PATH = Path.home() / ".gemstonecabfinder-private" / "plants.db"

# Each species has three pieces of advice: moisture checks, warning signs and general care.
CARE = {
    "Monstera": ("Let the upper 3–5 cm of compost dry, then check that the pot feels lighter before watering.", "Yellowing lower leaves and persistently wet compost can signal overwatering; brown crispy edges may mean dry air or underwatering.", "Give bright indirect light, a chunky draining mix, and a pot with drainage holes."),
    "Pothos": ("Wait until the upper few centimetres are dry and the pot is noticeably lighter.", "Yellow leaves and soft stems may indicate wet roots; limp leaves with dry soil suggest thirst.", "Bright indirect light and a free-draining potting mix help."),
    "Snake plant": ("Allow the compost to dry completely throughout the pot before watering.", "Soft or mushy leaves suggest excess moisture; wrinkled leaves with fully dry soil can suggest thirst.", "Use gritty free-draining compost and avoid water collecting in the crown."),
    "ZZ plant": ("Let the compost dry thoroughly; its rhizomes store water.", "Yellow soft stems or collapsing growth can indicate root rot.", "Keep in a draining pot, avoid frequent watering, and provide indirect light."),
    "Peace lily": ("Check moisture below the surface; water when the top few centimetres dry, before prolonged wilting.", "Drooping may mean either dry or waterlogged roots; yellow leaves can indicate excess water.", "Use moderate indirect light and drain away standing water."),
    "Spider plant": ("Water when the upper few centimetres are dry and the pot is getting lighter.", "Brown tips can reflect salts, dry air or inconsistent watering; yellow soft leaves suggest excess moisture.", "Bright indirect light and occasional flushing of the compost can help."),
    "Orchid (Phalaenopsis)": ("Check roots through a clear pot: silvery roots and a light pot often indicate it's time; green roots usually mean wait.", "Soft brown roots suggest rot; leathery wrinkled leaves may reflect root problems, not just thirst.", "Use orchid bark, good airflow and bright indirect light; drain fully."),
    "Aloe vera": ("Allow the compost to dry all the way through before watering deeply.", "Translucent mushy leaves suggest too much water; thin curling leaves with dry compost may indicate thirst.", "Give strong light, gritty compost and drainage."),
    "Calathea / Goeppertia": ("Keep lightly moist but never soggy; check just below the surface rather than following a fixed schedule.", "Crispy edges can reflect dry air, water quality or inconsistent moisture; yellowing may indicate wet roots.", "Use gentle indirect light, stable warmth and well-aerated compost."),
    "Ficus elastica (rubber plant)": ("Let the top 3–5 cm dry and check the pot weight.", "Leaf drop may follow abrupt changes; yellow leaves and soggy compost can indicate overwatering.", "Give bright indirect light and avoid cold draughts."),
    "String of pearls": ("Wait until the compost is fully dry and pearls begin to lose some firmness.", "Mushy pearls suggest excess water; shrivelled pearls with dry compost may indicate thirst.", "Provide very bright light, shallow free-draining compost and excellent drainage."),
    "Cactus / succulent": ("Let the whole pot dry before watering; check moisture at depth, not just the surface.", "Soft translucent tissue suggests rot; stretched growth indicates insufficient light.", "Use a gritty mix, drainage and appropriate bright light."),
    "Other / not sure": ("Check moisture several centimetres down and the pot's weight; do not water merely because a date has passed.", "Watch for yellowing, wilting despite wet compost, pests, browning and changes in growth.", "Identify the species for more specific advice; ensure drainage and suitable light."),
}
# Merge the original collection's species-specific advice into the general care dictionary.
CARE.update(INITIAL_CARE)


# Open the plant database and initialise missing tables; callers are responsible for closing the connection.
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(DB_PATH.parent, 0o700)
    if DB_PATH.is_symlink():
        raise RuntimeError("Plant database cannot be a symlink")
    conn = sqlite3.connect(DB_PATH)
    os.chmod(DB_PATH, 0o600)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS houseplants (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, species TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS plant_watering (
        id INTEGER PRIMARY KEY, plant_id INTEGER NOT NULL REFERENCES houseplants(id) ON DELETE CASCADE,
        watered_on TEXT NOT NULL, recorded_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS plant_moisture (
        plant_id INTEGER NOT NULL REFERENCES houseplants(id) ON DELETE CASCADE,
        checked_on TEXT NOT NULL, moisture TEXT NOT NULL, recorded_at TEXT NOT NULL,
        PRIMARY KEY (plant_id, checked_on))""")
    # Enable foreign-key enforcement so deleting a plant also removes its watering history.
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("CREATE TABLE IF NOT EXISTS plant_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    # Seed the initial collection only once, avoiding duplicate names and preventing deleted plants from reappearing.
    if not conn.execute("SELECT 1 FROM plant_metadata WHERE key='initial_collection_seeded'").fetchone():
        with conn:
            for name in INITIAL_PLANTS:
                if not conn.execute("SELECT 1 FROM houseplants WHERE name=? COLLATE NOCASE", (name,)).fetchone():
                    conn.execute("INSERT INTO houseplants(name,species,notes,created_at) VALUES (?,?,?,?)",
                                 (name, name, "", datetime.now(timezone.utc).isoformat()))
            conn.execute("INSERT INTO plant_metadata(key,value) VALUES ('initial_collection_seeded','1')")
    return conn


# Check the source host of write requests to reduce cross-site edits; this is not a separate login system.
def protected(fn):
    """No login; reject cross-site writes to reduce unwanted edits."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method == "POST":
            origin = request.headers.get("Origin") or request.headers.get("Referer", "")
            target = urlsplit(origin)
            if target.scheme not in ("https", "http") or target.netloc != request.host:
                abort(403)
        return fn(*args, **kwargs)
    return wrapper


@plants.get("/plants")
@protected
# Load the plant list and most recent recorded watering date for each plant.
def index():
    with closing(connection()) as conn:
        entries = conn.execute("""SELECT p.*, (SELECT MAX(watered_on) FROM plant_watering w WHERE w.plant_id=p.id) AS last_watered
                                  FROM houseplants p ORDER BY p.name COLLATE NOCASE, p.id""").fetchall()
        # Load all histories in two queries, rather than querying each plant separately.
        watering = defaultdict(list)
        moisture = defaultdict(list)
        for row in conn.execute("SELECT plant_id, watered_on FROM plant_watering ORDER BY watered_on DESC"):
            watering[row["plant_id"]].append(row["watered_on"])
        for row in conn.execute("SELECT * FROM plant_moisture ORDER BY checked_on DESC"):
            moisture[row["plant_id"]].append(row)
    today = date.today()
    # Use April through September as spring/summer and the remaining months as autumn/winter.
    season = "spring/summer" if 4 <= today.month <= 9 else "autumn/winter"
    with closing(connection()) as conn:
        setting = conn.execute("SELECT value FROM plant_metadata WHERE key='room_temperature'").fetchone()
    # Use the saved room temperature category, falling back to normal if absent or invalid.
    temperature = setting["value"] if setting and setting["value"] in ("cool", "normal", "warm") else "normal"
    guides = {}
    for plant in entries:
        # Calculate elapsed calendar days since watering; None means there is no recorded watering date.
        days_since = (today - date.fromisoformat(plant["last_watered"])).days if plant["last_watered"] else None
        interval = CHECK_INTERVALS.get(plant["species"])
        if interval:
            # Choose the seasonal pair of moisture-check intervals from the species guide.
            lower, upper = interval[:2] if season == "spring/summer" else interval[2:]
            # Lengthen check intervals by about 30 percent in cool rooms; shorten them by about 25 percent in warm rooms.
            if temperature == "cool":
                lower, upper = round(lower * 1.3), round(upper * 1.3)
            elif temperature == "warm":
                lower, upper = max(1, round(lower * 0.75)), max(1, round(upper * 0.75))
            guidance = f"Check moisture roughly every {lower}–{upper} days"
            # Override the generic drying guidance for this moisture-loving carnivorous plant.
            if plant["species"] == "Cape sundew":
                guidance = "Check the water tray daily or every other day; keep its compost wet"
        else:
            guidance = "Check soil moisture regularly; no species-specific interval yet"
        dates = sorted(set(watering[plant["id"]]))
        intervals = [(date.fromisoformat(b)-date.fromisoformat(a)).days for a,b in zip(dates,dates[1:])]
        guides[plant["id"]] = {"days_since": days_since, "guidance": guidance,
            "watering": list(reversed(dates)), "moisture": moisture[plant["id"]],
            "average": round(mean(intervals),1) if intervals else None,
            "shortest": min(intervals) if intervals else None,
            "longest": max(intervals) if intervals else None}
    # Pass plant records, care advice and calculated guidance to the page template.
    return render_template("plants.html", entries=entries, care=CARE, species=list(CARE),
                           today=today.isoformat(), season=season, temperature=temperature, guides=guides)


@plants.post("/plants/temperature")
@protected
# Validate and save the room temperature preference, then redirect to the refreshed plant list.
def set_temperature():
    value = request.form.get("temperature")
    if value not in ("cool", "normal", "warm"):
        abort(400)
    with closing(connection()) as conn:
        with conn:
            conn.execute("INSERT OR REPLACE INTO plant_metadata(key,value) VALUES ('room_temperature',?)", (value,))
    return redirect(url_for("plants.index"), code=303)


@plants.post("/plants/add")
@protected
# Validate the submitted name, species and notes before inserting a new plant.
def add():
    name = request.form.get("name", "").strip()
    species = request.form.get("species", "")
    notes = request.form.get("notes", "").strip()
    if not name or len(name) > 100 or len(notes) > 1000 or species not in CARE:
        abort(400)
    with closing(connection()) as conn:
        with conn:
            conn.execute("INSERT INTO houseplants(name,species,notes,created_at) VALUES (?,?,?,?)",
                         (name, species, notes, datetime.now(timezone.utc).isoformat()))
    return redirect(url_for("plants.index"), code=303)


@plants.post("/plants/<int:plant_id>/water")
@protected
# Record watering for an existing plant using the selected calendar date.
def water(plant_id):
    day = request.form.get("watered_on", "")
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        abort(400)
    # Reject future dates, dates before 2000 and non-canonical date formats.
    if parsed > date.today() or parsed.year < 2000 or parsed.isoformat() != day:
        abort(400)
    with closing(connection()) as conn:
        with conn:
            if not conn.execute("SELECT 1 FROM houseplants WHERE id=?", (plant_id,)).fetchone():
                abort(404)
            # Insert only if this plant has no watering record for that date, preventing repeated submissions from adding duplicates.
            conn.execute("""INSERT INTO plant_watering(plant_id,watered_on,recorded_at)
                SELECT ?,?,? WHERE NOT EXISTS (
                    SELECT 1 FROM plant_watering WHERE plant_id=? AND watered_on=?)""",
                (plant_id, day, datetime.now(timezone.utc).isoformat(), plant_id, day))
    return redirect(url_for("plants.index"), code=303)


@plants.post("/plants/<int:plant_id>/delete")
@protected
# Delete the selected plant; foreign-key cascading also removes its associated watering records.
def delete(plant_id):
    with closing(connection()) as conn:
        with conn:
            conn.execute("DELETE FROM houseplants WHERE id=?", (plant_id,))
    return redirect(url_for("plants.index"), code=303)


@plants.post("/plants/<int:plant_id>/moisture")
@protected
def record_moisture(plant_id):
    # Record an observation, not an instruction to water. One editable observation per day.
    day = request.form.get("checked_on", "")
    moisture = request.form.get("moisture", "")
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        abort(400)
    if parsed > date.today() or parsed.year < 2000 or parsed.isoformat() != day:
        abort(400)
    if moisture not in ("Wet", "Moist", "Almost dry", "Dry"):
        abort(400)
    with closing(connection()) as conn:
        with conn:
            if not conn.execute("SELECT 1 FROM houseplants WHERE id=?", (plant_id,)).fetchone():
                abort(404)
            conn.execute("""INSERT INTO plant_moisture(plant_id,checked_on,moisture,recorded_at)
                VALUES (?,?,?,?) ON CONFLICT(plant_id,checked_on) DO UPDATE SET
                moisture=excluded.moisture, recorded_at=excluded.recorded_at""",
                (plant_id,day,moisture,datetime.now(timezone.utc).isoformat()))
    return redirect(url_for("plants.index")+"#plant-"+str(plant_id), code=303)
