import pytest

from pretix_cz_banktransfer.models import CzechBankTransferCounter, CzechBankTransferReference
from pretix_cz_banktransfer.payment import CzechBankTransfer
from pretix_cz_banktransfer.reference import get_or_create_reference


@pytest.mark.django_db
def test_reference_is_numeric_stable_unique_and_short(cz_env):
    organizer, event, make_order = cz_env
    first = get_or_create_reference(make_order("AAAAA"))
    again = get_or_create_reference(first.order)
    second = get_or_create_reference(make_order("BBBBB"))
    assert first.pk == again.pk
    assert first.variable_symbol.isdigit()
    assert len(first.variable_symbol) <= 10
    assert first.variable_symbol != second.variable_symbol


@pytest.mark.django_db
def test_allocator_explicitly_skips_collision(cz_env):
    organizer, event, make_order = cz_env
    occupied_order = make_order("AAAAA")
    CzechBankTransferReference.objects.create(
        order=occupied_order, organizer=organizer, variable_symbol="1"
    )
    CzechBankTransferCounter.objects.create(organizer=organizer, next_value=1)
    allocated = get_or_create_reference(make_order("BBBBB"))
    assert allocated.variable_symbol == "2"


@pytest.mark.django_db
def test_reference_uses_prefix_and_remains_stable(cz_env):
    organizer, event, make_order = cz_env
    order = make_order("AAAAA")
    reference = get_or_create_reference(order, prefix="42")
    assert reference.variable_symbol == "421"
    assert get_or_create_reference(order, prefix="99").variable_symbol == "421"


@pytest.mark.django_db
def test_prefix_keeps_variable_symbol_within_ten_digits(cz_env):
    organizer, event, make_order = cz_env
    CzechBankTransferCounter.objects.create(organizer=organizer, next_value=9999)
    reference = get_or_create_reference(make_order("AAAAA"), prefix="123456")
    assert reference.variable_symbol == "1234569999"


@pytest.mark.django_db
def test_provider_uses_event_variable_symbol_prefix(cz_env):
    organizer, event, make_order = cz_env
    event.settings.payment_czbanktransfer_variable_symbol_prefix = "73"
    reference = CzechBankTransfer(event)._code(make_order("AAAAA"))
    assert reference == "731"
