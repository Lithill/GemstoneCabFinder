# Gemstone names used by the legacy title filter and search-term generation.
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
    "cosmic swirl",
    "wrasse snake skin",
    "opalized petrified wood",
]

# Build generic and gemstone-specific search terms, removing duplicates while retaining order.
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

# Retain the existing search limit, plus the newly requested gemstones.
SEARCH_TERMS = list(dict.fromkeys(SEARCH_TERMS[:12] + [
    "cosmic swirl",
    "wrasse snake skin",
    "opalized petrified wood",
]))

# Human-readable country names for the legacy search settings display.
TARGET_COUNTRIES = [
    "India",
    "United States",
    "Indonesia",
    "United Kingdom",
]

# Words used to distinguish finished jewellery from loose stones.
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

# Phrases suggesting the pictured stone is the actual item offered.
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

# Phrases suggesting random selection or representative photographs.
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

# Minimum seller eligibility thresholds.
MIN_SHOP_AGE_DAYS = 365
MIN_SHOP_RATING = 4.5
MIN_SHOP_REVIEWS = 20
# Maximum marketplace listings requested per search term; zero shop inventory limit disables that optional scan.
MAX_LISTINGS_TO_SEARCH = 300
MAX_SHOP_LISTINGS_TO_SEARCH = 0
# Allowed shipping-origin country codes, distinct from the buyer destination.
TARGET_SHIPPING_COUNTRIES = {"IN", "US", "ID", "GB"}

# UK delivery requirements
DELIVERY_COUNTRY = "GB"
MAX_UK_POSTAGE_GBP = 10.00