from collections import OrderedDict

from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.utils.translation import gettext, gettext_lazy as _
from i18nfield.fields import I18nFormField
from i18nfield.strings import LazyI18nString
from localflavor.generic.forms import IBANFormField

from pretix.base.forms import I18nMarkdownTextarea
from pretix.base.templatetags.money import money_filter
from pretix.plugins.banktransfer.payment import BankTransfer

from .reference import get_or_create_reference
from .spd import generate_spd, spd_qr_data_uri


class CzechBankTransfer(BankTransfer):
    identifier = "czbanktransfer"
    verbose_name = _("Bankovní převod (CZ)")

    @property
    def settings_form_fields(self):
        fields = OrderedDict(super().settings_form_fields)
        for key in (
            "bank_details_type", "bank_details_sepa_name", "bank_details_sepa_iban",
            "bank_details_sepa_bic", "bank_details_sepa_bank", "bank_details",
            "omit_hyphen", "include_invoice_number", "prefix",
        ):
            fields.pop(key, None)
        fields.update(OrderedDict((
            ("domestic_account_number", forms.CharField(label=_("Domestic account number"))),
            ("bank_code", forms.RegexField(r"^\d{4}$", label=_("Bank code"))),
            ("iban", IBANFormField(label=_("IBAN"))),
            ("recipient_name", forms.CharField(label=_("Account holder / recipient name"), required=False)),
            ("variable_symbol_prefix", forms.RegexField(
                r"^\d{0,6}$",
                label=_("Variable symbol prefix"),
                help_text=_(
                    "Optional organizer or event prefix of up to six digits. "
                    "The remaining digits are allocated automatically."
                ),
                required=False,
            )),
            ("instructions", I18nFormField(
                label=_("Additional payment instructions"), widget=I18nMarkdownTextarea,
                widget_kwargs={"attrs": {"rows": 4}}, required=False,
            )),
        )))
        return fields

    def settings_form_clean(self, cleaned_data):
        account = cleaned_data.get("payment_czbanktransfer_domestic_account_number", "")
        if account and not all(part.isdigit() for part in account.split("-")):
            raise ValidationError({"payment_czbanktransfer_domestic_account_number": _("Enter a Czech account number using digits and an optional hyphen.")})
        return cleaned_data

    def _code(self, order, force=False):
        if order is None:
            return None
        return get_or_create_reference(
            order, prefix=self.settings.get("variable_symbol_prefix", default="")
        ).variable_symbol

    def payment_prepare(self, request, payment):
        get_or_create_reference(
            payment.order,
            prefix=self.settings.get("variable_symbol_prefix", default=""),
        )
        return super().payment_prepare(request, payment)

    def _context(self, payment):
        variable_symbol = self._code(payment.order, force=True)
        payload = generate_spd(
            self.settings.iban,
            payment.amount,
            self.event.currency,
            variable_symbol,
            message=payment.order.full_code,
        )
        return {
            "event": self.event,
            "order": payment.order,
            "payment": payment,
            "amount": payment.amount,
            "variable_symbol": variable_symbol,
            "domestic_account": f"{self.settings.domestic_account_number}/{self.settings.bank_code}",
            "recipient_name": self.settings.recipient_name,
            "instructions": self.settings.get("instructions", as_type=LazyI18nString),
            "spd": payload,
            "qr_code": spd_qr_data_uri(payload),
        }

    def payment_form_render(self, request, total=None, order=None):
        return get_template("pretix_cz_banktransfer/checkout_payment_form.html").render({
            "order": order,
            "event": self.event,
            "amount": total if total is not None else (order.pending_sum if order else None),
            "variable_symbol": self._code(order) if order else None,
            "domestic_account": f"{self.settings.domestic_account_number}/{self.settings.bank_code}",
            "recipient_name": self.settings.recipient_name,
        }, request=request)

    def payment_pending_render(self, request, payment):
        return get_template("pretix_cz_banktransfer/pending.html").render(self._context(payment), request=request)

    def order_pending_mail_render(self, order, payment):
        ctx = self._context(payment)
        lines = [
            gettext("Please transfer the full amount to the following bank account:"), "",
            f"**{gettext('Account number')}:** {ctx['domestic_account']}  ",
            f"**{gettext('Amount')}:** {money_filter(payment.amount, self.event.currency)}  ",
            f"**{gettext('Variable symbol')}:** {ctx['variable_symbol']}",
        ]
        if ctx["recipient_name"]:
            lines.append(f"  \n**{gettext('Recipient')}:** {ctx['recipient_name']}")
        if ctx["instructions"]:
            lines.extend(("", str(ctx["instructions"])))
        return "\n".join(lines)
