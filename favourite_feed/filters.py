"""Title filters shared by the future grid and swipe views."""
import re
import html
import unicodedata

# Default words and phrases that hide unwanted listings from the unseen feed.
DEFAULT_EXCLUSIONS = (
    "wire wrapped", "wholesale lot", "bead", "beads", "pcs",
    "pieces", "coffin", "faceted", "fordite", "surfite",
    "mohave", "rose cut",
    # Finished jewellery; whole-word matching preserves terms such as "ring size".
    "ring", "rings", "necklace", "necklaces", "earring", "earrings",
    "bracelet", "bracelets", "pendant", "pendants", "choker", "chokers",
    "bangle", "bangles", "brooch", "brooches", "anklet", "anklets",
    "jewelry set", "jewellery set", "jewelry sets", "jewellery sets",
    "cufflinks", "tie clip", "tie clips", "stud earrings",
)
# Preferred loose-stone terms used when preferred-only mode is enabled.
DEFAULT_PREFERENCES = ("cabochon", "cab", "slab", "slice",
                       "cabochons", "cabs", "slabs", "slices")


# Decode HTML entities, normalise Unicode and case, then turn punctuation into word boundaries.
def normalize(value):
    value = unicodedata.normalize("NFKC", html.unescape(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


# Match complete words or phrases rather than fragments inside unrelated words.
def matching_terms(title, terms):
    normalized = " " + normalize(title) + " "
    return [term for term in terms
            if normalize(term) and " " + normalize(term) + " " in normalized]


# Apply exclusions first unless overridden, then require a preferred term only in preferred-only mode.
def is_visible(title, exclusions=DEFAULT_EXCLUSIONS,
               preferences=DEFAULT_PREFERENCES, preferred_only=False,
               show_excluded=False):
    if not show_excluded and matching_terms(title, exclusions):
        return False
    return not preferred_only or bool(matching_terms(title, preferences))
