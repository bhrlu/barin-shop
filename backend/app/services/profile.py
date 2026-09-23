"""Customer profile helpers (F5.20).

The single place the profile's validation rules live: the Iranian national ID
checksum, birth-date bounds and the closed gender / fit-preference sets. The
routers (`routers/auth.py` for the identity profile, `routers/profile.py` for
the size profile) call these — validation is never re-derived per route.

National ID (کد ملی) is **optional**: the store never blocks signup, checkout or
anything else because it is missing. When supplied it must be a valid 10-digit
Iranian national code (including the checksum); it is normalised to bare ASCII
digits (Persian/Arabic digits accepted, separators stripped) before anything
else sees it, and stored as TEXT so leading zeros survive. The database adds
only a shape CHECK (`^[0-9]{10}$`); the checksum lives here.

Measurements are centimetres, weight kilograms — the same units the DDL CHECK
constraints enforce; the bounds below mirror them so a 422 explains what the
database would otherwise reject with a 500.
"""

import re
from datetime import date

# Persian/Arabic digits → ASCII, then everything that is not a digit is stripped
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_NON_DIGITS = re.compile(r"[^0-9]")

GENDERS = ("male", "female", "other")
FIT_PREFERENCES = ("slim", "regular", "relaxed")

# Realistic human ranges; identical to the DDL CHECKs in `app/db.py` (F5.20).
# Generous on purpose — reject only the absurd.
HEIGHT_RANGE = (100, 230)
WEIGHT_RANGE = (30, 250)
CHEST_RANGE = (60, 160)
WAIST_RANGE = (50, 160)
HIP_RANGE = (60, 180)

BIRTH_DATE_MIN = date(1900, 1, 1)


def normalize_national_id(value: str | None) -> str | None:
    """Normalise a national ID to bare ASCII digits, or None when empty.

    Accepts Persian/Arabic digits and ignores spaces/dashes; «۰۴۹۳۷۲۱۸۲۳» and
    «0493-721823» both become «0493721823». Raises ValueError when what remains
    is not 10 digits or fails the checksum.
    """
    if value is None:
        return None
    digits = _NON_DIGITS.sub("", value.strip().translate(_FA_DIGITS))
    if not digits:
        return None
    if len(digits) != 10:
        raise ValueError("کد ملی باید دقیقاً ۱۰ رقم باشد")
    if not _valid_national_id_checksum(digits):
        raise ValueError("کد ملی واردشده معتبر نیست")
    return digits


def _valid_national_id_checksum(digits: str) -> bool:
    """The Iranian national-ID checksum.

    The first 9 digits weighted 10..2 sum + the check digit, mod 11: valid when
    the remainder is < 2 and equals the check digit, or the check digit is
    11 − remainder. Rejects the degenerate all-equal-digit codes (0000000000,
    1111111111, …) the arithmetic alone would accept.
    """
    if len(set(digits)) == 1:
        return False
    check = int(digits[9])
    total = sum(int(d) * w for d, w in zip(digits[:9], range(10, 1, -1), strict=True))
    remainder = total % 11
    return remainder < 2 and check == remainder or remainder >= 2 and check == 11 - remainder


def normalize_birth_date(value: date | None) -> date | None:
    """Bounds-check a birth date: not before 1900, not in the future."""
    if value is None:
        return None
    if value < BIRTH_DATE_MIN:
        raise ValueError("تاریخ تولد نمی‌تواند پیش از سال ۱۹۰۰ باشد")
    if value > date.today():
        raise ValueError("تاریخ تولد نمی‌تواند در آینده باشد")
    return value
