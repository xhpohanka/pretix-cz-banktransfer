from decimal import Decimal

import pytest

from pretix.base.models import Order, OrderPayment
from pretix.plugins.banktransfer.models import BankImportJob, BankTransaction
from pretix.plugins.banktransfer.tasks import process_banktransfers
from pretix_cz_banktransfer.reference import get_or_create_reference
from pretix_cz_banktransfer.signals import extract_variable_symbol
from pretix_cz_banktransfer.signals import resolve_czech_transaction


@pytest.mark.parametrize("text, expected", (
    ("VS = 123456789", "123456789"),
    ("Platba VS:123", "123"),
    ("variabilní symbol = 42", "42"),
    ("invoice 123456", None),
    ("VS=12A", None),
    ("VS=12345678901", None),
    ("VS=12 VS=13", None),
))
def test_conservative_vs_extraction(text, expected):
    assert extract_variable_symbol(text) == expected


@pytest.mark.django_db
def test_imported_vs_uses_standard_processing(cz_env):
    organizer, event, make_order = cz_env
    order = make_order("AAAAA")
    payment = order.payments.create(
        provider="czbanktransfer", amount=Decimal("1250.00"),
        state=OrderPayment.PAYMENT_STATE_PENDING,
    )
    reference = get_or_create_reference(order)
    job = BankImportJob.objects.create(event=event)
    process_banktransfers(job.pk, [{
        "payer": "Customer", "reference": f"VS = {reference.variable_symbol}",
        "date": "2026-08-14", "amount": "1250.00", "currency": "CZK",
    }])
    payment.refresh_from_db()
    order.refresh_from_db()
    transaction = BankTransaction.objects.get(import_job=job)
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED
    assert order.status == Order.STATUS_PAID
    assert transaction.state == BankTransaction.STATE_VALID
    assert transaction.order == order


@pytest.mark.django_db
@pytest.mark.parametrize("reference", ("VS=999999", "VS=bad", "number 1"))
def test_unknown_or_malformed_vs_does_not_match(cz_env, reference):
    organizer, event, make_order = cz_env
    job = BankImportJob.objects.create(event=event)
    process_banktransfers(job.pk, [{
        "payer": "Customer", "reference": reference,
        "date": "2026-08-14", "amount": "1250.00",
    }])
    assert BankTransaction.objects.get(import_job=job).state == BankTransaction.STATE_NOMATCH


@pytest.mark.django_db
def test_reference_does_not_match_another_organizer(cz_env):
    organizer, event, make_order = cz_env
    order = make_order("AAAAA")
    order.payments.create(
        provider="czbanktransfer", amount=Decimal("1250.00"),
        state=OrderPayment.PAYMENT_STATE_PENDING,
    )
    reference = get_or_create_reference(order)
    other = organizer.__class__.objects.create(name="Other", slug="other")
    assert resolve_czech_transaction(
        sender=other, transaction=None, organizer=other,
        reference=f"VS={reference.variable_symbol}",
    ) is None
