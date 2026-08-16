from decimal import Decimal

import pytest

from pretix.base.models import OrderPayment


def _settings(event):
    event.settings.payment_czbanktransfer_domestic_account_number = "185141554"
    event.settings.payment_czbanktransfer_bank_code = "0300"
    event.settings.payment_czbanktransfer_iban = "CZ4903000000000185141554"
    event.settings.payment_czbanktransfer_recipient_name = "Divadlo"


def _payment(order, state=OrderPayment.PAYMENT_STATE_PENDING):
    return order.payments.create(
        provider="czbanktransfer", amount=Decimal("1250.00"), state=state,
    )


@pytest.mark.django_db
def test_details_carry_everything_a_terminal_needs(cz_env):
    """
    The point-of-sale terminal only talks to the REST API, so this is the only
    way it can show a customer a QR code without reimplementing SPAYD itself.
    """
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("AAAAA")
    payment = _payment(order)
    details = payment.payment_provider.api_payment_details(payment)

    assert details["domestic_account"] == "185141554/0300"
    assert details["iban"] == "CZ4903000000000185141554"
    assert details["variable_symbol"].isdigit()
    assert details["spd"].startswith("SPD*1.0*ACC:CZ4903000000000185141554*AM:1250.00*CC:CZK*")
    assert details["variable_symbol"] in details["spd"]
    assert details["qr_code"].startswith("data:image/svg+xml;base64,")


@pytest.mark.django_db
@pytest.mark.parametrize("state, has_qr", (
    (OrderPayment.PAYMENT_STATE_CREATED, True),
    (OrderPayment.PAYMENT_STATE_PENDING, True),
    (OrderPayment.PAYMENT_STATE_CONFIRMED, False),
    (OrderPayment.PAYMENT_STATE_CANCELED, False),
    (OrderPayment.PAYMENT_STATE_FAILED, False),
))
def test_qr_is_only_rendered_while_the_payment_can_still_be_paid(cz_env, state, has_qr):
    """
    Every order fetched through the API serializes all of its payments, whole
    search-result lists included, so rendering a QR image for payments nobody
    will scan would put that cost on all of those requests. The account details
    stay available either way - they're cheap and still worth reading back.
    """
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("BBBBB")
    payment = _payment(order, state=state)

    details = payment.payment_provider.api_payment_details(payment)
    assert ("qr_code" in details) is has_qr
    assert details["variable_symbol"]
    assert details["spd"]
