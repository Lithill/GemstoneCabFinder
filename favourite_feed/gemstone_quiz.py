"""Conservative, title-based gemstone quiz classification.

A listing is eligible only when its title clearly names exactly one recognised
gemstone. Seller titles are not independently verified mineral identifications.
The distractors are curated visual lookalikes, not random gemstones.
"""
from functools import lru_cache
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

for _name in ["Agate","Jasper","Chalcedony","Quartz","Tourmaline","Topaz","Zircon","Spinel","Iolite","Morganite","Goshenite","Andalusite","Calcite","Azurite","Chrysocolla","Variscite","Howlite","Spectrolite","Larvikite","Shungite","Bronzite","Pietersite","Aventurine","Chalcopyrite","Marcasite","Rhodochrosite","Rhodonite","Charoite","Sugilite","Seraphinite","Prehnite","Chrysoprase","Bloodstone","Heliotrope","Unakite","Lepidolite","Mookaite","Kunzite","Hiddenite","Spodumene","Diopside","Chrome diopside","Sphene","Titanite","Sphalerite","Scapolite","Danburite","Phenakite","Petalite","Euclase","Benitoite","Alexandrite","Chrysoberyl","Beryl","Heliodor","Hessonite","Tsavorite","Demantoid","Spessartine","Almandine","Pyrope","Rhodolite","Uvarovite","Grossular","Ametrine","Prasiolite","Rutilated quartz","Tourmalinated quartz","Dendritic agate","Moss agate","Fire agate","Crazy lace agate","Blue lace agate","Botswana agate","Onyx","Sardonyx","Ocean jasper","Picture jasper","Dalmatian jasper","Kambaba jasper","Bumblebee jasper","Snowflake obsidian","Mahogany obsidian","Rainbow obsidian","Fire opal","Boulder opal","Black opal","Pink opal","White opal","Ethiopian opal","Rainbow moonstone","Peach moonstone","Green tourmaline","Pink tourmaline","Red tourmaline","Rubellite","Indicolite","Watermelon tourmaline","Paraiba tourmaline","Blue topaz","Imperial topaz","White topaz","Yellow sapphire","Blue sapphire","Pink sapphire","Purple sapphire","Padparadscha sapphire","Red spinel","Blue spinel","Purple fluorite","Green fluorite","Blue fluorite","Yellow fluorite","Clear fluorite","Hawk's eye","Serpentine","Jade","Jadeite","Nephrite","Amber","Jet","Coral","Pearl","Mother of pearl","Abalone","Ammolite","Ammonite","Orthoceras","Petrified wood","Moldavite","Tektite","Libyan desert glass","Selenite","Gypsum","Celestite","Celestine","Barite","Aragonite","Dolomite","Magnesite","Hematite","Magnetite","Goethite","Limonite","Cuprite","Bornite","Covellite","Galena","Smithsonite","Hemimorphite","Willemite","Wavellite","Vivianite","Epidote","Zoisite","Ruby zoisite","Ruby fuchsite","Fuchsite","Muscovite","Biotite","Orthoclase","Microcline","Feldspar","Hypersthene","Enstatite","Actinolite","Tremolite","Kornerupine","Axinite","Vesuvianite","Idocrase","Dumortierite","Sillimanite","Chiastolite","Staurolite","Lazulite","Lazurite","Hackmanite","Tugtupite","Eudialyte","Astrophyllite","Nuummite","Shattuckite","Ajoite","Plancheite","Dioptase","Atacamite","Ulexite","Natrolite","Stilbite","Heulandite","Apophyllite","Analcime","Thomsonite","Larimar","Pectolite","Atlantisite","Septarian","K2 granite","Yooperlite","Scolecite","Purpurite","Phosphosiderite","Tiffany stone","Chlorite","Shiva lingam","Herkimer diamond","Diamond"]:
    GEMS.setdefault(_name, ([_name.lower()], []))

GEMS.update({
    "Agatized dinosaur bone": [
        [
            "agatized dinosaur bone",
            "agtized dinosaur bone",
            "agatized dinosaur bone",
            "agatised dinosaur bone"
        ],
        [
            "Petrified palm wood",
            "Fossil coral agate",
            "Brecciated jasper"
        ]
    ],
    "Arfvedsonite": [
        [
            "arfvedsonite",
            "arfvedsonite"
        ],
        [
            "Larvikite",
            "Astrophyllite",
            "Labradorite"
        ]
    ],
    "Bloodstone": [
        [
            "bloodstone",
            "blood stone"
        ],
        [
            "Unakite",
            "Green jasper",
            "Moss agate"
        ]
    ],
    "Buffalo turquoise": [
        [
            "buffalo turquoise",
            "white buffalo turquoise",
            "white buffalo"
        ],
        [
            "Howlite",
            "Magnesite",
            "White jasper"
        ]
    ],
    "Chevron amethyst": [
        [
            "chevron amethyst",
            "chevron amethyst"
        ],
        [
            "Purple fluorite",
            "Purple agate",
            "Amethyst"
        ]
    ],
    "Fossil coral agate": [
        [
            "fossil coral agate",
            "coral fossil agate",
            "agatized coral"
        ],
        [
            "Ocean jasper",
            "Agatized dinosaur bone",
            "Petrified palm wood"
        ]
    ],
    "Crazy lace agate": [
        [
            "crazy lace agate"
        ],
        [
            "Botswana agate",
            "Picture jasper",
            "Maligano jasper"
        ]
    ],
    "Dalmatian jasper": [
        [
            "dalmatian jasper",
            "dalmation jasper"
        ],
        [
            "Snowflake obsidian",
            "Kambaba jasper",
            "Dendritic agate"
        ]
    ],
    "Dendrite fossil": [
        [
            "dendrite fossil",
            "dendrite fossil"
        ],
        [
            "Dendritic agate",
            "Dendritic opal",
            "Picture jasper"
        ]
    ],
    "Dendritic opal": [
        [
            "dendritic opal",
            "dendrite opal"
        ],
        [
            "Dendritic agate",
            "Dendrite fossil",
            "Moss agate"
        ]
    ],
    "Fire opal": [
        [
            "fire opal"
        ],
        [
            "Carnelian",
            "Orange calcite",
            "Spessartine"
        ]
    ],
    "Fordite": [
        [
            "fordite"
        ],
        [
            "Crazy lace agate",
            "Banded agate",
            "Rainbow calsilica"
        ]
    ],
    "Glacierite": [
        [
            "glacierite"
        ],
        [
            "Larimar",
            "Blue lace agate",
            "Blue chalcedony"
        ]
    ],
    "Grape agate": [
        [
            "grape agate"
        ],
        [
            "Botryoidal fluorite",
            "Amethyst",
            "Chalcedony"
        ]
    ],
    "Iolite sunstone": [
        [
            "iolite sunstone"
        ],
        [
            "Iolite",
            "Sunstone",
            "Tanzanite"
        ]
    ],
    "Larimar": [
        [
            "larimar"
        ],
        [
            "Turquoise",
            "Amazonite",
            "Blue chalcedony"
        ]
    ],
    "Larvikite": [
        [
            "larvikite"
        ],
        [
            "Labradorite",
            "Arfvedsonite",
            "Spectrolite"
        ]
    ],
    "Lepidocrocite": [
        [
            "lepidocrocite"
        ],
        [
            "Hematoid quartz",
            "Rutilated quartz",
            "Super seven"
        ]
    ],
    "Malachite chrysocolla": [
        [
            "malachite chrysocolla"
        ],
        [
            "Azurite-malachite",
            "Chrysocolla",
            "Turquoise"
        ]
    ],
    "Maligano jasper": [
        [
            "maligano jasper"
        ],
        [
            "Picture jasper",
            "Brecciated jasper",
            "Mookaite jasper"
        ]
    ],
    "Mookaite jasper": [
        [
            "mookaite jasper",
            "mookaite"
        ],
        [
            "Picture jasper",
            "Maligano jasper",
            "Crazy lace agate"
        ]
    ],
    "Moss agate": [
        [
            "moss agate"
        ],
        [
            "Dendritic agate",
            "Dendritic opal",
            "Bloodstone"
        ]
    ],
    "Ocean jasper": [
        [
            "ocean jasper"
        ],
        [
            "Kambaba jasper",
            "Fossil coral agate",
            "Crazy lace agate"
        ]
    ],
    "Opalised petrified wood": [
        [
            "opalised petrified wood",
            "opalized petrified wood"
        ],
        [
            "Petrified wood",
            "Petrified palm wood",
            "Picture jasper"
        ]
    ],
    "Peach moonstone": [
        [
            "peach moonstone"
        ],
        [
            "Sunstone",
            "Peach aventurine",
            "Rose quartz"
        ]
    ],
    "Petrified palm wood": [
        [
            "petrified palm wood"
        ],
        [
            "Agatized dinosaur bone",
            "Fossil coral agate",
            "Petrified wood"
        ]
    ],
    "Picture jasper": [
        [
            "picture jasper"
        ],
        [
            "Maligano jasper",
            "Mookaite jasper",
            "Petrified wood"
        ]
    ],
    "Pink conch shell": [
        [
            "pink conch shell"
        ],
        [
            "Pink coral",
            "Pink opal",
            "Spiny oyster"
        ]
    ],
    "Pink scolecite": [
        [
            "pink scolecite",
            "pink scolosite"
        ],
        [
            "Pink calcite",
            "Thomsonite",
            "Pink stilbite"
        ]
    ],
    "Pink tourmaline": [
        [
            "pink tourmaline"
        ],
        [
            "Morganite",
            "Pink sapphire",
            "Kunzite"
        ]
    ],
    "Prehnite": [
        [
            "prehnite"
        ],
        [
            "Chrysoprase",
            "Serpentine",
            "Jade"
        ]
    ],
    "Quartz": [
        [
            "quartz"
        ],
        [
            "Topaz",
            "Fluorite",
            "Calcite"
        ]
    ],
    "Rainbow moonstone": [
        [
            "rainbow moonstone"
        ],
        [
            "Moonstone",
            "Labradorite",
            "Opalite"
        ]
    ],
    "Serpentine": [
        [
            "serpentine"
        ],
        [
            "Nephrite",
            "Prehnite",
            "Chrysoprase"
        ]
    ],
    "Snowflake obsidian": [
        [
            "snowflake obsidian"
        ],
        [
            "Dalmatian jasper",
            "Black onyx",
            "Kambaba jasper"
        ]
    ],
    "Spiny oyster": [
        [
            "spiny oyster"
        ],
        [
            "Pink conch shell",
            "Coral",
            "Carnelian"
        ]
    ],
    "Super seven": [
        [
            "super seven"
        ],
        [
            "Lepidocrocite",
            "Rutilated quartz",
            "Hematoid quartz"
        ]
    ],
    "Unakite": [
        [
            "unakite"
        ],
        [
            "Bloodstone",
            "Ruby zoisite",
            "Green jasper"
        ]
    ],
    "Watermelon tourmaline": [
        [
            "watermelon tourmaline"
        ],
        [
            "Bicolour tourmaline",
            "Fluorite",
            "Watermelon quartz"
        ]
    ]
})
GEMS.pop("Mookaite", None)

GEMS.update({
    "Abalone": (["abalone"], ["Mother of pearl","Ammolite","Opal"]),
    "Afghanite": (["afghanite"], ["Lapis lazuli","Sodalite","Lazulite"]),
    "Ammolite": (["ammolite"], ["Abalone","Opal","Labradorite"]),
    "Aquaprase": (["aquaprase"], ["Chrysoprase","Gem silica","Turquoise"]),
    "Aragonite": (["aragonite"], ["Calcite","Yellow onyx","Selenite"]),
    "Aurora opal": (["aurora opal"], ["Opal","Opalite","Ammolite"]),
    "Azurite": (["azurite"], ["Lapis lazuli","Sodalite","Shattuckite"]),
    "Azurite-malachite": (["azurite-malachite","azurite malachite"], ["Malachite chrysocolla","Shattuckite","Azurite"]),
    "Banded agate": (["banded agate"], ["Botswana agate","Crazy lace agate","Onyx"]),
    "Binghamite": (["binghamite"], ["Tiger's eye","Pietersite","Bronzite"]),
    "Bird's eye jasper": (["bird's eye jasper","birds eye jasper"], ["Ocean jasper","Kambaba jasper","Picture jasper"]),
    "Cavansite": (["cavansite"], ["Azurite","Shattuckite","Blue apatite"]),
    "Chrysocolla": (["chrysocolla"], ["Turquoise","Gem silica","Shattuckite"]),
    "Crinoid fossil": (["crinoid fossil"], ["Fossil coral agate","Turritella jasper","Petrified palm wood"]),
    "Dendritic agate": (["dendritic agate","dendrite agate","dentritic agate"], ["Dendritic opal","Moss agate","Dendrite fossil"]),
    "Eudialyte": (["eudialyte"], ["Rhodonite","Ruby zoisite","Thulite"]),
    "Fire quartz": (["fire quartz","hematoid quartz"], ["Lepidocrocite","Carnelian","Super seven"]),
    "Gem silica": (["gem silica"], ["Aquaprase","Chrysocolla","Turquoise"]),
    "Iolite": (["iolite"], ["Tanzanite","Sapphire","Amethyst"]),
    "Jasper": (["jasper"], ["Agate","Rhyolite","Petrified wood"]),
    "Kammererite": (["kammererite","kämmererite"], ["Charoite","Lepidolite","Sugilite"]),
    "Lepidolite": (["lepidolite"], ["Charoite","Phosphosiderite","Kammererite"]),
    "Marcasite with pyrite": (["marcasite with pyrite"], ["Pyrite","Chalcopyrite","Schalenblende"]),
    "Mariposite": (["mariposite"], ["Fuchsite","Serpentine","Moss agate"]),
    "Meteorite": (["meteorite"], ["Hematite","Magnetite","Tektite"]),
    "Mohave turquoise": (["mohave turquoise","mojave turquoise"], ["Turquoise","Spiny oyster turquoise","Chrysocolla"]),
    "Moldavite": (["moldavite"], ["Green obsidian","Peridot","Green fluorite"]),
    "Moonstone with tourmaline": (["moonstone with tourmaline","moonstone with touramaline"], ["Tourmalinated quartz","Rainbow moonstone","Dendritic opal"]),
    "Moss plume agate": (["moss plume agate"], ["Moss agate","Plume agate","Dendritic agate"]),
    "Mother of pearl": (["mother of pearl"], ["Abalone","Moonstone","Opalite"]),
    "Mystic topaz": (["mystic topaz"], ["Mystic quartz","Ammolite","Titanium aura quartz"]),
    "Opalite": (["opalite"], ["Moonstone","Opal","White chalcedony"]),
    "Peacock zoisite": (["peacock zoisite","peacock ziosite"], ["Ruby zoisite","Tanzanite","Eudialyte"]),
    "Phosphosiderite": (["phosphosiderite"], ["Lepidolite","Sugilite","Charoite"]),
    "Pietersite": (["pietersite"], ["Tiger's eye","Binghamite","Hawk's eye"]),
    "Pinolith": (["pinolith"], ["Snowflake obsidian","Buffalo turquoise","Dalmatian jasper"]),
    "Plume agate": (["plume agate"], ["Moss agate","Dendritic agate","Moss plume agate"]),
    "Rainbow obsidian": (["rainbow obsidian"], ["Obsidian","Labradorite","Rainbow moonstone"]),
    "Rhodochrosite": (["rhodochrosite"], ["Rhodonite","Pink opal","Pink calcite"]),
    "Rhyolite": (["rhyolite"], ["Jasper","Ocean jasper","Kambaba jasper"]),
    "Rosarita": (["rosarita"], ["Carnelian","Red coral","Red jasper"]),
    "Ruby zoisite": (["ruby zoisite"], ["Ruby fuchsite","Unakite","Eudialyte"]),
    "Schalenblende": (["schalenblende"], ["Banded agate","Marcasite with pyrite","Binghamite"]),
    "Selenite": (["selenite"], ["Ulexite","Calcite","Clear quartz"]),
    "Seraphinite": (["seraphinite"], ["Serpentine","Mariposite","Fuchsite"]),
    "Shattuckite": (["shattuckite"], ["Azurite","Chrysocolla","Lapis lazuli"]),
    "Spiny oyster turquoise": (["spiny oyster turquoise","spin oyster turquoise"], ["Mohave turquoise","Spiny oyster","Fordite"]),
    "Sunstone lepidolite": (["sunstone lepidolite"], ["Sunstone","Lepidolite","Peach moonstone"]),
    "Surfite": (["surfite"], ["Fordite","Crazy lace agate","Rainbow calsilica"]),
    "Thulite": (["thulite"], ["Rhodonite","Rhodochrosite","Eudialyte"]),
    "Tiffany stone": (["tiffany stone"], ["Charoite","Purple fluorite","Phosphosiderite"]),
    "Titanium aura quartz": (["titanium aura quartz"], ["Mystic topaz","Bornite","Rainbow obsidian"]),
    "Topaz": (["topaz"], ["Quartz","Aquamarine","Citrine"]),
    "Tourmaline": (["tourmaline","touramaline"], ["Beryl","Topaz","Sapphire"]),
    "Trolleite": (["trolleite"], ["Blue quartz","Lazulite","Sodalite"]),
    "Turritella jasper": (["turritella jasper","turritella agate"], ["Crinoid fossil","Fossil coral agate","Agatized dinosaur bone"]),
    "Vivianite": (["vivianite"], ["Kyanite","Azurite","Blue tourmaline"]),
    "Wild horse jasper": (["wild horse jasper"], ["Buffalo turquoise","Picture jasper","Howlite"]),
    "Yellow onyx": (["yellow onyx"], ["Aragonite","Calcite","Banded agate"]),
})
GEMS["Carnelian"][0].append("carnelian chalcedony")
GEMS["Petrified palm wood"][0].extend(["fossilised palm wood", "fossilised palmwood", "petrified palm wood agate"])

GEMS.update({
    "Jade": (["jade"], ["Serpentine", "Chrysoprase", "Prehnite"]),
    "Lavender jade": (["lavender jade", "lavender jadeite", "purple jade"], ["Phosphosiderite", "Lepidolite", "Lavender chalcedony"]),
    "Jadeite": (["jadeite"], ["Nephrite", "Serpentine", "Chrysoprase"]),
    "Nephrite": (["nephrite"], ["Jadeite", "Serpentine", "Prehnite"]),
})
ALIASES = {alias.casefold(): name for name, (aliases, _) in GEMS.items() for alias in [name] + aliases}

# Translate a known alias to its standard stored name; leave unfamiliar names intact.
def canonical_name(name):
    return ALIASES.get(name.strip().casefold(), name.strip()) if name else name

# Exact saved-label corrections only; never match truncated words in titles.
LABEL_FIXES = {"buf": "Buffalo turquoise", "oce": "Ocean jasper", "mys": "Mystic topaz", "aurora o": "Aurora opal", "moss": "Moss agate"}
INCOMPLETE_LABELS = {"fire", "water", "mother", "titanium", "titani", "ioli", "lab", "tiffany"}

# Repair known incomplete saved labels only when the listing title provides an unambiguous answer.
def clean_label(name, title):
    key = name.strip().casefold()
    if key in INCOMPLETE_LABELS or key in LABEL_FIXES:
        # Resolve only from an unambiguous title; otherwise return to review.
        return identify(title) or None
    return canonical_name(name)

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


# Normalise the custom-name collection before using the cached title classifier.
def identify(title, custom=()):
    return _identify_cached(title, tuple(sorted(set(custom) - set(GEMS))))


@lru_cache(maxsize=8)
# Build regular expressions for custom names alongside the built-in patterns.
def _patterns_for(custom):
    patterns = dict(PATTERNS)
    for name in custom:
        patterns[name] = [re.compile(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", re.I)]
    return patterns


@lru_cache(maxsize=50000)
def _identify_cached(title, custom):
    """Return one unambiguous recognised seller-stated stone, or None."""
    if not title or UNSAFE.search(title):
        return None
    patterns = _patterns_for(custom)
    # Record each matched name and its character positions in the title.
    hits = [(name, m.start(), m.end()) for name, ps in patterns.items() for p in ps for m in p.finditer(title)]
    # Discard shorter matches contained inside longer ones, then deduplicate the remaining names.
    matches = list({name for name, a, b in hits if not any(c <= a and d >= b and (c < a or d > b) for _, c, d in hits)})
    # Ignore broad colour-only cases, e.g. 'turquoise blue' is not a stone.
    if "Turquoise" in matches and re.search(r"\bturquoise\s+(?:blue|green|colour|color)\b", title, re.I):
        matches.remove("Turquoise")
    return matches[0] if len(matches) == 1 else None


def options(name, seed, listing_id, available=None):
    """Return deterministic, shuffled multiple-choice options for a photo."""
    # Prefer plausible lookalikes from the available materials, filling gaps from curated alternatives.
    pool = set(GEMS) if available is None else set(available)
    preferred = list(dict.fromkeys(GEMS.get(name, ([], []))[1] + visual_alternatives(name)))
    answers = [name] + list(dict.fromkeys(gem for gem in preferred if gem in pool and gem != name))
    answers.extend(gem for gem in preferred if gem not in answers and len(answers) < 4)
    # Seed a local random generator using the session and listing ID so answer order stays consistent.
    rng = random.Random(int.from_bytes(hashlib.sha256(
        f"{seed}:{listing_id}:choices".encode("utf-8")).digest(), "big"))
    remaining = sorted(pool - set(answers))
    rng.shuffle(remaining)
    answers.extend(remaining[:max(0, 4-len(answers))])
    # Do not offer two names for the same underlying answer.
    seen = {material_info(name)["primary"].casefold()}
    unique = [name]
    for gem in answers[1:] + remaining:
        key = material_info(gem)["primary"].casefold()
        if key not in seen and len(unique) < 4 and not any(overlapping(gem, other) for other in unique):
            unique.append(gem)
            seen.add(key)
    rng.shuffle(unique)
    return unique

# Presentation only: keep stored quiz keys and preferences stable.
# These descriptions classify the named material, not the individual photograph.
DISPLAY_NAMES = {
    "Buffalo turquoise": ("White Buffalo stone", "White Buffalo turquoise"),
    "Wild horse jasper": ("Magnesite-rich stone (composition unverified)", "Wild Horse jasper"),
    "Herkimer diamond": ("Quartz", "Herkimer diamond"),
    "Rainbow moonstone": ("White labradorite", "Rainbow moonstone"),
    "Dalmatian jasper": ("Dalmatian stone", "Dalmatian jasper"),
    "Bumblebee jasper": ("Bumblebee stone", "Bumblebee jasper"),
    "Kambaba jasper": ("Kambaba stone", "Kambaba jasper"),
    "Turritella jasper": ("Fossil snail agate", "Turritella jasper, Turritella agate"),
    "Yellow onyx": ("Banded carbonate (usually calcite)", "Yellow onyx"),
    "Fire quartz": ("Hematoid quartz", "Fire quartz"),
    "Smoky topaz": ("Smoky quartz", "Smoky topaz (misleading name)"),
    "Dendrite fossil": ("Dendritic stone (host unverified)", "Dendrite fossil"),
    "Sphene": ("Titanite", "Sphene"),
    "Titanite": ("Titanite", "Sphene"),
    "Idocrase": ("Vesuvianite", "Idocrase"),
    "Vesuvianite": ("Vesuvianite", "Idocrase"),
    "Celestite": ("Celestine", "Celestite"),
    "Celestine": ("Celestine", "Celestite"),
    "Heliotrope": ("Bloodstone", "Heliotrope"),
    "Bloodstone": ("Bloodstone", "Heliotrope"),
    "Larimar": ("Blue pectolite", "Larimar"),
    "Aquaprase": ("Blue-green chalcedony", "Aquaprase"),
    "Gem silica": ("Copper-coloured chalcedony", "Gem silica"),
    "Seraphinite": ("Clinochlore", "Seraphinite"),
    "Spectrolite": ("Labradorite", "Spectrolite"),
    "Iolite": ("Cordierite", "Iolite"),
    "Tanzanite": ("Blue-violet zoisite", "Tanzanite"),
    "Super seven": ("Included quartz", "Super Seven"),
    "Tiffany stone": ("Fluorite-rich mixed rock (typically)", "Tiffany stone"),
    "Grape agate": ("Botryoidal chalcedony", "Grape agate"),
    "Fordite": ("Layered automotive paint", "Fordite"),
    "Surfite": ("Layered surfboard resin", "Surfite"),
    "Rosarita": ("Glassy industrial by-product", "Rosarita"),
    "Opalite": ("Opalescent glass (usually)", "Opalite"),
    "Aurora opal": ("Manufactured opal material (typically)", "Aurora opal"),
    "Mohave turquoise": ("Reconstructed or composite turquoise (typically)", "Mohave turquoise"),
    "Spiny oyster turquoise": ("Shell and turquoise composite", "Spiny oyster turquoise"),
    "Mystic topaz": ("Coated topaz", "Mystic topaz"),
    "Titanium aura quartz": ("Metal-coated quartz", "Titanium aura quartz"),
    "Rainbow calsilica": ("Manufactured decorative material", "Rainbow calsilica"),
    "Dyed howlite": ("Dyed howlite", ""),
    "Shiva lingam": ("Polished stone (composition unverified)", "Shiva lingam"),
    "Peacock zoisite": ("Zoisite-bearing material (unverified)", "Peacock zoisite"),
    "Glacierite": ("Material unverified", "Glacierite"),
    "Sunstone lepidolite": ("Mineral mixture (unverified)", "Sunstone lepidolite"),
    "Iolite sunstone": ("Included cordierite (seller identification)", "Iolite sunstone"),
    "Atlantisite": ("Stichtite in serpentine", "Atlantisite"),
    "Yooperlite": ("Sodalite-bearing rock", "Yooperlite"),
    "K2 granite": ("Azurite-bearing granite", "K2 stone"),
}
# These sets group named materials by typical origin or treatment, not verified properties of a particular stone.
MANMADE = {"Fordite", "Surfite", "Rosarita", "Opalite", "Aurora opal", "Rainbow calsilica", "Watermelon quartz", "Mystic quartz"}
COMPOSITE = {"Mohave turquoise", "Spiny oyster turquoise"}
TREATED = {"Mystic topaz", "Titanium aura quartz", "Dyed howlite"}
UNCERTAIN = {"Glacierite", "Peacock zoisite", "Sunstone lepidolite", "Dendrite fossil", "Yellow onyx", "Shiva lingam", "Wild horse jasper", "Iolite sunstone"}
ORGANIC = {"Abalone", "Amber", "Jet", "Coral", "Pearl", "Mother of pearl", "Ammolite", "Ammonite", "Orthoceras", "Petrified wood", "Agatized dinosaur bone", "Fossil coral agate", "Petrified palm wood", "Opalised petrified wood", "Pink conch shell", "Spiny oyster", "Crinoid fossil", "Turritella jasper"}
# Return a display name, alternate trade name and cautious origin description.
def material_info(name):
    primary, alternate = DISPLAY_NAMES.get(name, (name or "", ""))
    if name in MANMADE:
        origin = "Man-made material (typical usage)"
    elif name in COMPOSITE:
        origin = "Man-made composite (typical usage)"
    elif name in TREATED:
        origin = "Treated natural material (seller identification)"
    elif name in UNCERTAIN or name not in GEMS:
        origin = "Origin or composition unverified"
    elif name in ORGANIC:
        origin = "Natural organic or fossil material (seller identification)"
    else:
        origin = "Natural mineral or rock type; treatment and authenticity unverified"
    return {"primary": primary, "alternate": alternate, "origin": origin}

# Combine the primary name and alternate name for display without changing the stored quiz key.
def display_answer(name):
    info = material_info(name)
    return info["primary"] + (" (" + info["alternate"] + ")" if info["alternate"] else "")

# Map each material to the category used by the quiz mode selector.
def material_category(name):
    if name in MANMADE or name in COMPOSITE or name in TREATED:
        return "manufactured"
    if name in UNCERTAIN or name not in GEMS:
        return "uncertain"
    if name in ORGANIC:
        return "organic"
    return "natural"

# Visual families provide relevant alternatives for entries without curated choices.
VISUAL_FAMILIES = [
    "Quartz|Clear quartz|White topaz|Goshenite|Danburite|Phenakite|Petalite|Euclase|Diamond|Clear fluorite|Herkimer diamond",
    "Amethyst|Purple fluorite|Purple sapphire|Iolite|Tanzanite|Kunzite|Lepidolite|Charoite|Sugilite|Purpurite|Phosphosiderite|Lavender jade|Kammererite",
    "Ruby|Red spinel|Garnet|Almandine|Pyrope|Rhodolite|Rubellite|Red tourmaline|Pink sapphire|Pink tourmaline|Morganite|Rhodonite|Rhodochrosite|Thulite|Eudialyte",
    "Emerald|Chrome diopside|Diopside|Tsavorite|Demantoid|Uvarovite|Green tourmaline|Peridot|Green fluorite|Hiddenite|Kornerupine|Vesuvianite|Idocrase|Epidote|Dioptase|Atacamite",
    "Citrine|Heliodor|Yellow topaz|Imperial topaz|Yellow sapphire|Yellow fluorite|Hessonite|Spessartine|Sphalerite|Titanite|Sphene|Amber|Fire opal|Carnelian",
    "Aquamarine|Blue topaz|Blue zircon|Blue sapphire|Blue spinel|Indicolite|Paraiba tourmaline|Benitoite|Blue fluorite|Apatite|Kyanite|Iolite",
    "Lapis lazuli|Sodalite|Lazulite|Lazurite|Azurite|Afghanite|Dumortierite|Cavansite|Shattuckite|Plancheite|Trolleite|Hackmanite",
    "Turquoise|Chrysocolla|Variscite|Aquaprase|Gem silica|Larimar|Amazonite|Smithsonite|Hemimorphite|Ajoite|Pectolite",
    "Jade|Jadeite|Nephrite|Serpentine|Prehnite|Chrysoprase|Prasiolite|Grossular|Wavellite|Mariposite|Fuchsite|Actinolite|Tremolite",
    "Pyrite|Marcasite|Chalcopyrite|Bornite|Covellite|Galena|Hematite|Magnetite|Goethite|Cuprite|Limonite|Meteorite|Schalenblende",
    "Obsidian|Black onyx|Jet|Shungite|Black tourmaline|Tektite|Moldavite|Libyan desert glass|Mahogany obsidian|Rainbow obsidian",
    "Tiger's eye|Hawk's eye|Bronzite|Hypersthene|Enstatite|Pietersite|Binghamite|Nuummite|Astrophyllite|Arfvedsonite",
    "Moonstone|Rainbow moonstone|Peach moonstone|Labradorite|Spectrolite|Larvikite|Feldspar|Orthoclase|Microcline|Sunstone|Opalite",
    "Calcite|Aragonite|Dolomite|Magnesite|Howlite|Barite|Gypsum|Selenite|Ulexite|Celestite|Celestine|Natrolite|Scolecite|Stilbite|Heulandite|Apophyllite|Analcime|Thomsonite",
    "Agate|Chalcedony|Banded agate|Botswana agate|Blue lace agate|Crazy lace agate|Onyx|Sardonyx|Plume agate|Moss agate|Dendritic agate|Dendritic opal",
    "Jasper|Picture jasper|Mookaite jasper|Maligano jasper|Rhyolite|Ocean jasper|Kambaba jasper|Bumblebee jasper|Dalmatian jasper|Pinolith|Septarian|K2 granite|Yooperlite|Unakite|Bloodstone|Heliotrope",
    "Opal|White opal|Black opal|Boulder opal|Ethiopian opal|Pink opal|Fire opal|Ammolite|Abalone|Mother of pearl|Aurora opal",
    "Petrified wood|Petrified palm wood|Agatized dinosaur bone|Fossil coral agate|Crinoid fossil|Ammonite|Orthoceras|Turritella jasper",
    "Rutilated quartz|Tourmalinated quartz|Lepidocrocite|Fire quartz|Super seven|Chlorite|Ajoite",
    "Andalusite|Axinite|Smoky quartz|Scapolite|Staurolite|Chiastolite|Sillimanite|Spodumene|Beryl|Zircon",
    "Muscovite|Biotite|Fuchsite|Lepidolite|Chlorite|Seraphinite",
    "Fordite|Surfite|Rainbow calsilica|Spiny oyster turquoise|Mohave turquoise",
]
# Find other recognised gemstones in the same visual families and remove duplicates.
def visual_alternatives(name):
    return list(dict.fromkeys(gem for family in VISUAL_FAMILIES for gem in family.split("|") if name in family.split("|") and gem != name and gem in GEMS))

# Check for identical or simple overlapping primary names to reduce ambiguous answer choices.
def overlapping(a, b):
    a, b = material_info(a)["primary"].casefold(), material_info(b)["primary"].casefold()
    return a == b or a in b.split() or b in a.split()
