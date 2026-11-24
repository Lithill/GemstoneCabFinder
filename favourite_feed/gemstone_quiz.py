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

ALIASES = {alias.casefold(): name for name, (aliases, _) in GEMS.items() for alias in [name] + aliases}

def canonical_name(name):
    return ALIASES.get(name.casefold(), name) if name else name

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


def identify(title, custom=()):
    return _identify_cached(title, tuple(sorted(set(custom) - set(GEMS))))


@lru_cache(maxsize=8)
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
    hits = [(name, m.start(), m.end()) for name, ps in patterns.items() for p in ps for m in p.finditer(title)]
    matches = list({name for name, a, b in hits if not any(c <= a and d >= b and (c < a or d > b) for _, c, d in hits)})
    # Ignore broad colour-only cases, e.g. 'turquoise blue' is not a stone.
    if "Turquoise" in matches and re.search(r"\bturquoise\s+(?:blue|green|colour|color)\b", title, re.I):
        matches.remove("Turquoise")
    return matches[0] if len(matches) == 1 else None


def options(name, seed, listing_id, available=None):
    """Return deterministic, shuffled multiple-choice options for a photo."""
    pool = set(GEMS) if available is None else set(available)
    preferred = GEMS.get(name, ([], []))[1]
    answers = [name] + list(dict.fromkeys(gem for gem in preferred if gem in pool and gem != name))
    answers.extend(gem for gem in preferred if gem not in answers and len(answers) < 4)
    rng = random.Random(int.from_bytes(hashlib.sha256(
        f"{seed}:{listing_id}:choices".encode("utf-8")).digest(), "big"))
    remaining = sorted(pool - set(answers))
    rng.shuffle(remaining)
    answers.extend(remaining[:max(0, 4-len(answers))])
    rng.shuffle(answers)
    return answers
