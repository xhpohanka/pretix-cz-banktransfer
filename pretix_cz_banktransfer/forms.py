from django import forms
from django.utils.translation import gettext_lazy as _
from i18nfield.fields import I18nFormField
from localflavor.generic.forms import IBANFormField

from pretix.base.forms import I18nMarkdownTextarea, SettingsForm


class CzechBankTransferOrganizerSettingsForm(SettingsForm):
    payment_czbanktransfer__enabled = forms.BooleanField(
        label=_("Enable Czech bank transfer by default"), required=False,
    )
    payment_czbanktransfer_domestic_account_number = forms.CharField(
        label=_("Domestic account number"), required=False,
    )
    payment_czbanktransfer_bank_code = forms.RegexField(
        r"^\d{4}$", label=_("Bank code"), required=False,
    )
    payment_czbanktransfer_iban = IBANFormField(label=_("IBAN"), required=False)
    payment_czbanktransfer_recipient_name = forms.CharField(
        label=_("Account holder / recipient name"), required=False,
    )
    payment_czbanktransfer_variable_symbol_prefix = forms.RegexField(
        r"^\d{0,6}$",
        label=_("Variable symbol prefix"),
        help_text=_(
            "Optional organizer or event prefix of up to six digits. "
            "The remaining digits are allocated automatically."
        ),
        required=False,
    )
    payment_czbanktransfer_instructions = I18nFormField(
        label=_("Additional payment instructions"),
        widget=I18nMarkdownTextarea,
        widget_kwargs={"attrs": {"rows": 4}},
        required=False,
    )

    def clean_payment_czbanktransfer_domestic_account_number(self):
        account = self.cleaned_data["payment_czbanktransfer_domestic_account_number"]
        if account and not all(part.isdigit() for part in account.split("-")):
            raise forms.ValidationError(
                _("Enter a Czech account number using digits and an optional hyphen.")
            )
        return account

    def clean(self):
        data = super().clean()
        if not data.get("payment_czbanktransfer__enabled"):
            return data

        for field in (
            "payment_czbanktransfer_domestic_account_number",
            "payment_czbanktransfer_bank_code",
            "payment_czbanktransfer_iban",
        ):
            if not data.get(field):
                self.add_error(field, _("This field is required when Czech bank transfer is enabled."))
        return data
