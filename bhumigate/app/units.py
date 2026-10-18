"""Land-area units used in Bangladesh, converted to the canonical unit: decimal (শতাংশ).

Unit mix-ups between deeds and khatians are a classic source of area mismatch,
so every area in the system is stored as decimals and converted at the edges.

ASSUMPTION: 1 katha = 720 sq ft (Dhaka-style). The katha varies by region in
practice; change KATHA_SQFT to model another region.
"""

SQFT_PER_DECIMAL = 435.6
KATHA_SQFT = 720.0

UNIT_TO_DECIMAL = {
    "decimal": 1.0,
    "acre": 100.0,
    "katha": KATHA_SQFT / SQFT_PER_DECIMAL,
    "bigha": 20 * KATHA_SQFT / SQFT_PER_DECIMAL,
    "sqft": 1.0 / SQFT_PER_DECIMAL,
}

UNIT_BN = {
    "decimal": "শতাংশ",
    "acre": "একর",
    "katha": "কাঠা",
    "bigha": "বিঘা",
    "sqft": "বর্গফুট",
}

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def to_decimal(value: float, unit: str) -> float:
    if unit not in UNIT_TO_DECIMAL:
        raise ValueError(f"unknown unit: {unit}")
    return value * UNIT_TO_DECIMAL[unit]


def from_decimal(value: float, unit: str) -> float:
    if unit not in UNIT_TO_DECIMAL:
        raise ValueError(f"unknown unit: {unit}")
    return value / UNIT_TO_DECIMAL[unit]


def bn_num(text) -> str:
    """Render ASCII digits as Bangla digits."""
    return str(text).translate(BN_DIGITS)
