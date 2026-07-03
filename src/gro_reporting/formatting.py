"""Deutsche Zahlen/Waehrungs/Datum-Formatierung ohne locale-Abhaengigkeit."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def format_number(n: int | float | Decimal) -> str:
    """1234567 -> '1.234.567'"""
    if isinstance(n, float):
        n = int(round(n))
    if isinstance(n, Decimal):
        n = int(n.to_integral_value(rounding=ROUND_HALF_UP))
    s = f"{abs(n):,}".replace(",", ".")
    return f"-{s}" if n < 0 else s


# Anzeige-Symbol je Waehrungscode; unbekannte Codes werden 1:1 angezeigt
CURRENCY_SYMBOLS = {"EUR": "€", "CHF": "CHF"}


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency)


def format_currency(n: float | Decimal, show_cents: bool = True, currency: str = "EUR") -> str:
    """1234.56 -> '€ 1.234,56' bzw. 'CHF 1.234,56'"""
    symbol = currency_symbol(currency)
    if not isinstance(n, Decimal):
        n = Decimal(str(n))
    n = n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if n < 0 else ""
    n = abs(n)
    integer_part = int(n)
    cents = int((n - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", ".")
    if show_cents:
        return f"{sign}{symbol} {int_str},{cents:02d}"
    return f"{sign}{symbol} {int_str}"


def format_percent(n: float | Decimal) -> str:
    """3.52 -> '3,52 %'"""
    if not isinstance(n, Decimal):
        n = Decimal(str(n))
    n = n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    formatted = str(n).replace(".", ",")
    return f"{formatted} %"


def format_date(d: date) -> str:
    """date(2026, 1, 1) -> '01.01.2026'"""
    return d.strftime("%d.%m.%Y")


def format_date_short(d: date) -> str:
    """date(2026, 4, 8) -> '08.04.'"""
    return d.strftime("%d.%m.")


def format_month_year(d: date) -> str:
    """date(2026, 4, 1) -> 'April, 2026'"""
    months = {
        1: "Jänner", 2: "Februar", 3: "März", 4: "April",
        5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
    }
    return f"{months[d.month]}, {d.year}"


def format_currency_suffix(n: float | Decimal, show_cents: bool = True, currency: str = "EUR") -> str:
    """1234.56 -> '1.234,56 €' bzw. '1.234,56 CHF'"""
    symbol = currency_symbol(currency)
    if not isinstance(n, Decimal):
        n = Decimal(str(n))
    n = n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if n < 0 else ""
    n = abs(n)
    integer_part = int(n)
    cents = int((n - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", ".")
    if show_cents:
        return f"{sign}{int_str},{cents:02d} {symbol}"
    return f"{sign}{int_str} {symbol}"


def format_roas(n: float | Decimal) -> str:
    """9.66 -> '9,66'"""
    if not isinstance(n, Decimal):
        n = Decimal(str(n))
    n = n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(n).replace(".", ",")
