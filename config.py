GEMSTONES = [
    "labradorite",
    "moss agate",
    "jasper",
    "turquoise",
    "malachite",
    "opal",
    "chrysocolla",
    "pietersite",
    "montana agate",
    "stick agate",
    "shattuckite",
    "bacan",
    "petrified wood",
    "maligano",
    "astrophyllite",
    "golden rutile",
    "hypersthene",
    "goldstone",
    "mookaite",
    "rosita",
    "dendritic",
    "schalenblende",
    "ocean jasper",
    "ammolite",
    "septarian",
    "agate",
    "marcasite",
    "palm root",
    "iolite",
    "dendrite",
    "larimar",
    "afghanite",
    "azurite",
    "apatite",
    "glacierite",
    "onyx",
    "moonstone",
    "tourmaline",
    "zebra calcite",
    "nellite",
    "fluorite",
    "charoite",
]

SEARCH_TERMS = list(dict.fromkeys(
    [
        "gemstone cabochon",
        "natural stone cabochon",
        "loose gemstone cabochon",
        "cabochon",
    ]
    + GEMSTONES
    + [f"{gemstone} cabochon" for gemstone in GEMSTONES]
))

SEARCH_TERMS = SEARCH_TERMS[:12]

TARGET_COUNTRIES = [
    "India",
    "United States",
    "Indonesia",
    "United Kingdom",
]

FINISHED_JEWELLERY_TERMS = [
    "ring",
    "rings",
    "pendant",
    "pendants",
    "necklace",
    "necklaces",
    "earring",
    "earrings",
    "bracelet",
    "bracelets",
    "brooch",
    "brooches",
    "jewelry set",
    "jewellery set",
]

WYSIWYG_POSITIVE_PHRASES = [
    "wysiwyg",
    "exact stone pictured",
    "exact stone shown",
    "exact gemstone pictured",
    "you will receive the stone pictured",
    "you will receive the exact stone",
    "stone in the photos",
    "actual stone pictured",
]

WYSIWYG_NEGATIVE_PHRASES = [
    "randomly selected",
    "random selection",
    "chosen at random",
    "random stone",
    "similar stone",
    "similar gemstone",
    "stock photo",
    "representative photo",
    "stone may vary",
    "color may vary",
    "colour may vary",
]

MIN_SHOP_AGE_DAYS = 365
MIN_SHOP_RATING = 4.5
MIN_SHOP_REVIEWS = 20
MAX_LISTINGS_TO_SEARCH = 300
MAX_SHOP_LISTINGS_TO_SEARCH = 0
TARGET_SHIPPING_COUNTRIES = {"IN", "US", "ID", "GB"}