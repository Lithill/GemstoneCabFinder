"""Conservative, title-based gemstone quiz classification.

A listing is eligible only when its title clearly names exactly one recognised
gemstone. Seller titles are not independently verified mineral identifications.
The distractors are curated visual lookalikes, not random gemstones.
"""
import hashlib
import random
import re

# Canonical name: (title aliases, three plausible lookalikes).
GEMS = {
    "Amethyst": (["amethyst"], ["Purple fluorite", "Iolite", "Purple sapphire"]),
    "Aquamarine": (["aquamarine"], ["Blue topaz", "Blue zircon", "Pale blue sapphire"]),
    "Citrine": (["citrine"], ["Yellow topaz", "Yellow sapphire", "Yellow fluorite"]),
    "Emerald": (["emerald"], ["Green tourmaline", "Peridot", "Green fluorite"]),
    "Ruby": (["ruby", "rubies"], ["Red spinel", "Garnet", "Red tourmaline"]),
    "Sapphire": (["sapphire"], ["Iolite", "Blue spinel", "Tanzanite"]),
    "Peridot": (["peridot"], ["Green tourmaline", "Green garnet", "Green fluorite"]),
    "Garnet": (["garnet"], ["Ruby", "Red spinel", "Red tourmaline"]),
    "Labradorite": (["labradorite"], ["Moonstone", "Spectrolite", "Larvikite"]),
    "Moonstone": (["moonstone"], ["Labradorite", "Opalite", "White chalcedony"]),
    "Black tourmaline": (["black tourmaline", "schorl"], ["Obsidian", "Black onyx", "Shungite"]),
    "Obsidian": (["obsidian"], ["Black tourmaline", "Black onyx", "Shungite"]),
    "Black onyx": (["black onyx"], ["Obsidian", "Black tourmaline", "Black agate"]),
    "Rose quartz": (["rose quartz"], ["Morganite", "Pink opal", "Pink calcite"]),
    "Smoky quartz": (["smoky quartz", "smokey quartz"], ["Smoky topaz", "Brown zircon", "Andalusite"]),
    "Clear quartz": (["clear quartz", "rock crystal"], ["White topaz", "Goshenite", "Clear fluorite"]),
    "Fluorite": (["fluorite", "fluorspar"], ["Amethyst", "Calcite", "Apatite"]),
    "Malachite": (["malachite"], ["Chrysocolla", "Green jasper", "Azurite-malachite"]),
    "Lapis lazuli": (["lapis lazuli", "lapis"], ["Sodalite", "Azurite", "Blue jasper"]),
    "Sodalite": (["sodalite"], ["Lapis lazuli", "Azurite", "Blue jasper"]),
    "Turquoise": (["turquoise"], ["Chrysocolla", "Variscite", "Dyed howlite"]),
    "Tiger's eye": (["tiger's eye", "tigers eye", "tiger eye"], ["Hawk's eye", "Bronzite", "Pietersite"]),
    "Carnelian": (["carnelian", "cornelian"], ["Orange agate", "Sunstone", "Orange calcite"]),
    "Sunstone": (["sunstone"], ["Carnelian", "Peach moonstone", "Orange aventurine"]),
    "Kyanite": (["kyanite"], ["Blue sapphire", "Blue tourmaline", "Iolite"]),
    "Tanzanite": (["tanzanite"], ["Iolite", "Blue sapphire", "Purple spinel"]),
    "Opal": (["opal"], ["Opalite", "Moonstone", "White labradorite"]),
    "Amazonite": (["amazonite"], ["Turquoise", "Chrysocolla", "Aquamarine"]),
    "Apatite": (["apatite"], ["Aquamarine", "Blue tourmaline", "Blue fluorite"]),
    "Pyrite": (["pyrite"], ["Chalcopyrite", "Marcasite", "Gold"]),
}

# Match longer phrases first so "black tourmaline" isn't confused with
# a generic term. Generic gemstone words in colour phrases are avoided.
PATTERNS = {
    name: [re.compile(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", re.I)
           for alias in aliases]
    for name, (aliases, _) in GEMS.items()
}

# A title may describe sets, mixes, lookalikes or simulated stones.
UNSAFE = re.compile(
    r"\b(?:assorted|mixed|mix of|variety pack|gemstone lot|imitation|"
    r"simulated|faux|synthetic|lab[- ]?created|lab[- ]?grown|"
    r"glass|resin|dyed|lookalike|style|inspired)\b", re.I
)


def identify(title):
    """Return one unambiguous recognised seller-stated stone, or None."""
    if not title or UNSAFE.search(title):
        return None
    matches = [name for name, patterns in PATTERNS.items()
               if any(pattern.search(title) for pattern in patterns)]
    # Ignore broad colour-only cases, e.g. 'turquoise blue' is not a stone.
    if "Turquoise" in matches and re.search(r"\bturquoise\s+(?:blue|green|colour|color)\b", title, re.I):
        matches.remove("Turquoise")
    return matches[0] if len(matches) == 1 else None


def options(name, seed, listing_id):
    """Return deterministic, shuffled multiple-choice options for a photo."""
    if name not in GEMS:
        return []
    answers = [name] + GEMS[name][1]
    rng = random.Random(int.from_bytes(hashlib.sha256(
        f"{seed}:{listing_id}:choices".encode("utf-8")).digest(), "big"))
    rng.shuffle(answers)
    return answers
