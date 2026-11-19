"""Title filters shared by the future grid and swipe views."""
import re
import html
import unicodedata

DEFAULT_EXCLUSIONS = (
    "wire wrapped", "wholesale lot", "bead", "beads", "pcs",
    "pieces", "coffin", "faceted", "fordite", "surfite",
    "mohave", "rose cut",
)
DEFAULT_PREFERENCES = ("cabochon", "cab", "slab", "slice",
                       "cabochons", "cabs", "slabs", "slices")


def normalize(value):
    value = unicodedata.normalize("NFKC", html.unescape(value or "")).casefold()
    return " ".join(re.findall(r"[^\W_]+", value, flags=re.UNICODE))


def matching_terms(title, terms):
    normalized = " " + normalize(title) + " "
    return [term for term in terms
            if normalize(term) and " " + normalize(term) + " " in normalized]


def is_visible(title, exclusions=DEFAULT_EXCLUSIONS,
               preferences=DEFAULT_PREFERENCES, preferred_only=False,
               show_excluded=False):
    if not show_excluded and matching_terms(title, exclusions):
        return False
    return not preferred_only or bool(matching_terms(title, preferences))
