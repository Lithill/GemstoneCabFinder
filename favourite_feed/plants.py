"""Separate, opt-in, password-protected houseplant diary.

No gemstone tables are touched. Routes return 503 until a password hash is set.
"""
from datetime import date, datetime, timezone
from functools import wraps
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from urllib.parse import urlsplit

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

plants = Blueprint("plants", __name__)
DB_PATH = Path.home() / ".gemstonecabfinder-private" / "plants.db"

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
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def protected(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        hashed = os.environ.get("PLANTS_PASSWORD_HASH", "")
        if not hashed:
            return "Houseplant diary is not configured yet.", 503
        auth = request.authorization
        if not auth or auth.type.lower() != "basic" or auth.username != "plants" or not check_password_hash(hashed, auth.password or ""):
            return Response("Sign in to your private houseplant diary.", 401, {"WWW-Authenticate": 'Basic realm="Houseplant diary", charset="UTF-8"'})
        if request.method == "POST":
            origin = request.headers.get("Origin", "")
            if not origin or urlsplit(origin).scheme != "https" or urlsplit(origin).netloc != request.host:
                abort(403)
        return fn(*args, **kwargs)
    return wrapper


@plants.get("/plants")
@protected
def index():
    with closing(connection()) as conn:
        entries = conn.execute("""SELECT p.*, (SELECT MAX(watered_on) FROM plant_watering w WHERE w.plant_id=p.id) AS last_watered
                                  FROM houseplants p ORDER BY p.name COLLATE NOCASE, p.id""").fetchall()
    return render_template("plants.html", entries=entries, care=CARE, species=list(CARE))


@plants.post("/plants/add")
@protected
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
def water(plant_id):
    day = request.form.get("watered_on", "")
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        abort(400)
    if parsed > date.today() or parsed.year < 2000:
        abort(400)
    with closing(connection()) as conn:
        with conn:
            if not conn.execute("SELECT 1 FROM houseplants WHERE id=?", (plant_id,)).fetchone():
                abort(404)
            conn.execute("INSERT INTO plant_watering(plant_id,watered_on,recorded_at) VALUES (?,?,?)",
                         (plant_id, day, datetime.now(timezone.utc).isoformat()))
    return redirect(url_for("plants.index"), code=303)


@plants.post("/plants/<int:plant_id>/delete")
@protected
def delete(plant_id):
    with closing(connection()) as conn:
        with conn:
            conn.execute("DELETE FROM houseplants WHERE id=?", (plant_id,))
    return redirect(url_for("plants.index"), code=303)
