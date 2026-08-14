from decimal import Decimal

import pytest

from pretix_cz_banktransfer.spd import generate_spd


def test_spd_contains_iban_payment_amount_currency_and_vs():
    assert generate_spd(
        "CZ65 0300 0000 0001 2345 6789", Decimal("1250"), "czk", "123456789"
    ) == "SPD*1.0*ACC:CZ6503000000000123456789*AM:1250.00*CC:CZK*X-VS:123456789"


def test_spd_contains_order_identifier_in_recipient_message():
    assert generate_spd(
        "CZ6503000000000123456789", Decimal("1250"), "CZK", "123456789",
        message="EVENT-ABCDE",
    ).endswith("*MSG:EVENT-ABCDE")


@pytest.mark.parametrize("value", ("", "12A", "12345678901"))
def test_spd_rejects_malformed_vs(value):
    with pytest.raises(ValueError):
        generate_spd("CZ6503000000000123456789", Decimal("1"), "CZK", value)
