"""Month/year helpers: parsing of user input and month boundaries."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

MIN_YEAR = 1900
MAX_YEAR = 2100


def parse_year_month(year_raw: str | None, month_raw: str | None) -> date:
    """Return the first day of the month. Raise ValueError with a user-facing message on invalid input."""
    try:
        if year_raw is None or month_raw is None:
            raise ValueError
        year, month = int(year_raw), int(month_raw)
    except ValueError:
        raise ValueError("Укажите месяц и год числами") from None
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"Год должен быть в диапазоне {MIN_YEAR}–{MAX_YEAR}")
    if not 1 <= month <= 12:
        raise ValueError("Месяц должен быть от 1 до 12")
    return date(year, month, 1)


def parse_period_slug(slug: str) -> date:
    """'2023-12' -> date(2023, 12, 1). Raise ValueError for any other format."""
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", slug):
        raise ValueError(f"Invalid period: {slug!r}")
    return date.fromisoformat(f"{slug}-01")


def period_slug(period: date) -> str:
    return period.strftime("%Y-%m")


def current_year() -> int:
    """The current year in UTC, the time zone of the database session."""
    return datetime.now(UTC).year


def next_month(period: date) -> date:
    return date(period.year + 1, 1, 1) if period.month == 12 else date(period.year, period.month + 1, 1)
