"""Bangla name normalisation and similarity.

Bangla names have many harmless spelling variants (মোঃ / মোহাম্মদ, ই-কার / ঈ-কার,
স / শ / ষ ...). We normalise those away before comparing, so that a lookalike
impostor (a different identity token with a near-identical name and father's
name) can be told apart from an honest spelling difference.
"""

from difflib import SequenceMatcher

_PREFIXES = ["মোহাম্মদ", "মুহাম্মদ", "মোসাম্মৎ", "মোসাম্মত", "মোছাঃ", "মোঃ", "মো."]
_FOLD = {
    "ী": "ি", "ূ": "ু", "ঈ": "ই", "ঊ": "উ",
    "শ": "স", "ষ": "স", "ণ": "ন", "ৎ": "ত",
    "ব্দু": "বদু",
}


def bn_normalize(name: str) -> str:
    s = name.strip()
    for p in _PREFIXES:
        s = s.replace(p, "")
    for a, b in _FOLD.items():
        s = s.replace(a, b)
    return "".join(s.split())


def similarity(a: str, b: str) -> float:
    na, nb = bn_normalize(a), bn_normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()
