import re
from config import FINISHED_JEWELLERY_TERMS, WYSIWYG_POSITIVE_PHRASES, WYSIWYG_NEGATIVE_PHRASES

def classify_wysiwyg(title, description="", rare_find=False):
    """Classify evidence that the buyer receives the pictured stone."""
    text = (str(title) + " " + str(description)).casefold()

    for phrase in WYSIWYG_NEGATIVE_PHRASES:
        if phrase in text:
            return "Likely random selection"

    for phrase in WYSIWYG_POSITIVE_PHRASES:
        if phrase in text:
            return "Likely WYSIWYG"

    if rare_find:
        return "Possible WYSIWYG - Rare find"

    return "Needs checking"

def is_loose_cabochon(title):
    title = title.casefold()

    if "cabochon" not in title and "cabochons" not in title:
        return False

    # Phrases suggesting the listing sells loose stones
    loose_stone_phrases = [
        "loose",
        "flat back",
        "flatback",
        "calibrated",
        "for jewelry making",
        "for jewellery making",
        "jewelry supply",
        "jewellery supply",
        "gemstone lot",
        "cabochon lot",
    ]

    # Remove loose-stone phrases before checking jewellery terms.
    # This protects phrases such as "for ring making".
    if "for ring making" in title:
        title = title.replace("for ring making", "")

    if "for pendant making" in title:
        title = title.replace("for pendant making", "")

    # Check for clear evidence that the listing sells loose stones
    is_loose_stone = any(
        phrase in title for phrase in loose_stone_phrases
    )

    # Check whether the title mentions finished jewellery
    is_finished_jewellery = any(
        re.search(r"\b" + re.escape(term) + r"\b", title)
        for term in FINISHED_JEWELLERY_TERMS
    )

    # Keep listings clearly described as loose stones
    if is_loose_stone:
        return True

    # Exclude listings mentioning finished jewellery
    if is_finished_jewellery:
        return False

    return True



EVIDENCE_RANK = {"Likely random selection": 0, "Needs checking": 1, "Possible WYSIWYG - Rare find": 2, "Likely WYSIWYG": 3}
