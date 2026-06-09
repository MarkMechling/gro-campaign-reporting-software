from datetime import date
from decimal import Decimal

from gro_reporting.formatting import (
    format_currency,
    format_date,
    format_date_short,
    format_month_year,
    format_number,
    format_percent,
    format_roas,
)


class TestFormatNumber:
    def test_simple(self):
        assert format_number(1234) == "1.234"

    def test_large(self):
        assert format_number(784185) == "784.185"

    def test_millions(self):
        assert format_number(1234567) == "1.234.567"

    def test_small(self):
        assert format_number(42) == "42"

    def test_zero(self):
        assert format_number(0) == "0"

    def test_negative(self):
        assert format_number(-1234) == "-1.234"

    def test_decimal(self):
        assert format_number(Decimal("338544")) == "338.544"


class TestFormatCurrency:
    def test_basic(self):
        assert format_currency(Decimal("1347.27")) == "€ 1.347,27"

    def test_small(self):
        assert format_currency(Decimal("0.11")) == "€ 0,11"

    def test_large(self):
        assert format_currency(Decimal("3797.96")) == "€ 3.797,96"

    def test_no_cents(self):
        assert format_currency(Decimal("1429.00")) == "€ 1.429,00"

    def test_float_input(self):
        assert format_currency(62.30) == "€ 62,30"

    def test_without_cents(self):
        assert format_currency(Decimal("22900.00"), show_cents=False) == "€ 22.900"


class TestFormatPercent:
    def test_basic(self):
        assert format_percent(Decimal("3.52")) == "3,52 %"

    def test_large(self):
        assert format_percent(Decimal("27.55")) == "27,55 %"

    def test_small(self):
        assert format_percent(Decimal("2.09")) == "2,09 %"

    def test_float_input(self):
        assert format_percent(3.90) == "3,90 %"


class TestFormatDate:
    def test_basic(self):
        assert format_date(date(2026, 1, 1)) == "01.01.2026"

    def test_end_of_month(self):
        assert format_date(date(2026, 4, 8)) == "08.04.2026"


class TestFormatDateShort:
    def test_basic(self):
        assert format_date_short(date(2026, 1, 1)) == "01.01."

    def test_april(self):
        assert format_date_short(date(2026, 4, 8)) == "08.04."


class TestFormatMonthYear:
    def test_april(self):
        assert format_month_year(date(2026, 4, 1)) == "April, 2026"

    def test_january(self):
        assert format_month_year(date(2026, 1, 1)) == "Jänner, 2026"

    def test_march(self):
        assert format_month_year(date(2026, 3, 1)) == "März, 2026"


class TestFormatRoas:
    def test_basic(self):
        assert format_roas(Decimal("9.66")) == "9,66"

    def test_calculation(self):
        roas = (Decimal("22900") / Decimal("2368.96")).quantize(Decimal("0.01"))
        assert format_roas(roas) == "9,67"
