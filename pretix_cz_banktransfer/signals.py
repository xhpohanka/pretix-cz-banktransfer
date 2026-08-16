import logging
import re
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import SafeMIMEText
from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext, gettext_lazy as _

from pretix.base.i18n import language
from pretix.base.models import OrderPayment
from pretix.base.signals import email_filter, register_payment_providers
from pretix.control.signals import nav_organizer
from pretix.plugins.banktransfer.signals import resolve_transaction

from .models import CzechBankTransferReference
from .payment import CzechBankTransfer
from .spd import spd_qr_png

logger = logging.getLogger(__name__)


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


@receiver(nav_organizer, dispatch_uid="czbanktransfer_nav_organizer")
def nav_organizer_settings(sender, request, organizer, **kwargs):
    if not request.user.has_organizer_permission(
        organizer, "organizer.settings.general:write", request=request
    ):
        return []

    url = resolve(request.path_info)
    return [{
        "label": _("Czech bank transfer"),
        "url": reverse(
            "plugins:pretix_cz_banktransfer:settings",
            kwargs={"organizer": organizer.slug},
        ),
        "parent": reverse("control:organizer.edit", kwargs={"organizer": organizer.slug}),
        "active": url.namespace == "plugins:pretix_cz_banktransfer" and url.url_name == "settings",
    }]


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


# Height in CSS pixels the code is rendered at in the mail. spd_qr_png()'s own
# default produces a somewhat larger bitmap on purpose, so the image still looks
# sharp on a high-density phone screen while occupying this much of the layout.
QR_MAIL_WIDTH = 246


def _payment_awaiting_transfer(order):
    return order.payments.filter(
        provider=CzechBankTransfer.identifier,
        state__in=(OrderPayment.PAYMENT_STATE_CREATED, OrderPayment.PAYMENT_STATE_PENDING),
    ).order_by("-local_id").first()


def _related_multipart(message):
    """
    The multipart/related container pretix builds for the HTML alternative (see
    mail_send_task) - that's where an inline image has to live for a mail client
    to resolve a cid: reference to it.
    """
    for alternative in getattr(message, "alternatives", None) or []:
        # Django 5.2 made alternatives a namedtuple; older versions use a plain
        # (content, mimetype) tuple.
        content = getattr(alternative, "content", None) or alternative[0]
        mimetype = getattr(alternative, "mimetype", None) or alternative[1]
        if mimetype == "multipart/related" and hasattr(content, "get_payload"):
            return content
    return None


def _insert_qr_into_html(html, cid, variable_symbol, caption, alt):
    """
    Puts the code directly after whatever block mentions the variable symbol -
    i.e. right below the payment instructions this plugin rendered - rather than
    at the end of the message, where it would land under the footer.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    holder = soup.new_tag("p")
    holder.append(soup.new_string(caption + " "))
    img = soup.new_tag("img", src="cid:%s" % cid, width=str(QR_MAIL_WIDTH))
    # Must not repeat the caption: a client that blocks images falls back to the
    # alt text, and the two together then read as the same sentence twice.
    img["alt"] = alt
    holder.append(img)

    text_node = soup.find(string=lambda s: variable_symbol in s)
    anchor = text_node.find_parent(["p", "td", "li", "div"]) if text_node else None
    if anchor is not None:
        anchor.insert_after(holder)
    elif soup.body is not None:
        soup.body.append(holder)
    else:
        return None
    return str(soup)


@receiver(email_filter, dispatch_uid="czbanktransfer_email_qr")
def add_qr_code_to_payment_mail(sender, message, order=None, **kwargs):
    """
    Puts the scannable code next to the account details in the mail that asks
    the customer to pay.

    It can't be added where those details are actually produced
    (order_pending_mail_render): pretix sanitises mail markdown with an allowlist
    that contains neither the img tag nor the data: protocol, so an image written
    there is stripped before it ever reaches a message. By this point the message
    is fully assembled, so the image is attached to its multipart/related part
    and referenced by content ID - the same shape core produces for images that
    were in the HTML from the start.

    Deliberately never lets a failure here stop a mail: payment instructions
    without a QR code are still perfectly usable, instructions that never arrive
    are not.
    """
    if order is None:
        return message

    try:
        payment = _payment_awaiting_transfer(order)
        if payment is None:
            return message

        provider = payment.payment_provider
        if not isinstance(provider, CzechBankTransfer):
            return message
        variable_symbol, payload = provider._spd_payload(payment)

        # Every mail for this order passes through here, most of which have
        # nothing to do with paying (order changed, ticket ready, ...). The
        # variable symbol appearing in the body is what identifies the one that
        # carries the instructions this code belongs to.
        if variable_symbol not in (message.body or ""):
            return message

        png = spd_qr_png(payload)
        # email_filter is not sent inside a language() context, unlike the
        # ticket/ical attachment steps just above it in mail_send_task - so
        # without this the caption comes out in whatever locale the worker
        # happens to be in (English) while the rest of the mail is the
        # customer's own.
        with language(order.locale, sender.settings.region):
            caption = gettext("Scan to pay:")
            alt = gettext("QR payment code")
        cid = "czbanktransfer-qr"

        related = _related_multipart(message)
        html_part = None
        if related is not None:
            for part in related.get_payload():
                if part.get_content_type() == "text/html":
                    html_part = part
                    break

        if html_part is None:
            # A plain-text-only event has no HTML part to embed into, so the
            # customer gets the code as a file instead of not at all.
            message.attach("qr-platba.png", png, "image/png")
            return message

        charset = html_part.get_content_charset() or settings.DEFAULT_CHARSET
        html = _insert_qr_into_html(
            html_part.get_payload(decode=True).decode(charset), cid, variable_symbol, caption, alt,
        )
        if html is None:
            message.attach("qr-platba.png", png, "image/png")
            return message

        parts = related.get_payload()
        parts[parts.index(html_part)] = SafeMIMEText(html, "html", charset)

        image = MIMEImage(png, _subtype="png")
        image.add_header("Content-ID", "<%s>" % cid)
        image.add_header("Content-Disposition", "inline", filename="qr-platba.png")
        related.attach(image)
    except Exception:
        logger.exception("Could not add a payment QR code to an outgoing mail")

    return message
