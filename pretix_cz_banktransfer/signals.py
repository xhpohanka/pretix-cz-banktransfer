import re

from django.dispatch import receiver

from pretix.base.models import OrderPayment
from pretix.base.signals import register_payment_providers
from pretix.plugins.banktransfer.signals import resolve_transaction

from .models import CzechBankTransferReference
from .payment import CzechBankTransfer


VS_PATTERNS = (
    re.compile(r"(?<![A-Z0-9])VS\s*[:=]\s*(\d{1,10})(?![A-Z0-9])", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])VARIABILN[IÍ]\s+SYMBOL\s*[:=]\s*(\d{1,10})(?![A-Z0-9])", re.IGNORECASE),
)


def extract_variable_symbol(reference):
    values = {match.group(1) for pattern in VS_PATTERNS for match in pattern.finditer(reference or "")}
    return values.pop() if len(values) == 1 else None


@receiver(register_payment_providers, dispatch_uid="payment_czbanktransfer")
def register_payment_provider(sender, **kwargs):
    return CzechBankTransfer


@receiver(resolve_transaction, dispatch_uid="czbanktransfer_resolve_transaction")
def resolve_czech_transaction(sender, transaction, organizer, event=None, reference="", **kwargs):
    variable_symbol = extract_variable_symbol(reference)
    if not variable_symbol:
        return None
    refs = CzechBankTransferReference.objects.select_related("order").filter(
        organizer=organizer, variable_symbol=variable_symbol,
    )
    if event:
        refs = refs.filter(order__event=event)
    ref = refs.first()
    if not ref:
        return None
    return ref.order.payments.filter(
        provider=CzechBankTransfer.identifier,
        state__in=(OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING),
    ).order_by("-local_id").first()
