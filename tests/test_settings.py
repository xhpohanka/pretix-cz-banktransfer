from django_scopes import scope

from pretix_cz_banktransfer.forms import CzechBankTransferOrganizerSettingsForm
from pretix_cz_banktransfer.payment import CzechBankTransfer


def test_organizer_settings_are_inherited_by_event(cz_env):
    organizer, event, _ = cz_env
    form = CzechBankTransferOrganizerSettingsForm(
        obj=organizer,
        data={
            "payment_czbanktransfer__enabled": "on",
            "payment_czbanktransfer_domestic_account_number": "123456789",
            "payment_czbanktransfer_bank_code": "0300",
            "payment_czbanktransfer_iban": "CZ6503000000000123456789",
            "payment_czbanktransfer_recipient_name": "Czech Organizer",
            "payment_czbanktransfer_variable_symbol_prefix": "73",
        },
    )
    assert form.is_valid(), form.errors
    form.save()

    with scope(organizer=organizer):
        provider = CzechBankTransfer(event)
        assert provider.settings.domestic_account_number == "123456789"
        assert provider.settings.bank_code == "0300"
        assert provider.settings.iban == "CZ6503000000000123456789"
        assert provider.settings.recipient_name == "Czech Organizer"
        assert provider.settings.variable_symbol_prefix == "73"


def test_enabled_organizer_settings_require_bank_details(cz_env):
    organizer, _, _ = cz_env
    form = CzechBankTransferOrganizerSettingsForm(
        obj=organizer,
        data={"payment_czbanktransfer__enabled": "on"},
    )
    assert not form.is_valid()
    assert set(form.errors) == {
        "payment_czbanktransfer_domestic_account_number",
        "payment_czbanktransfer_bank_code",
        "payment_czbanktransfer_iban",
    }
