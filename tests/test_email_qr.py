from decimal import Decimal

import pytest
from django.conf import settings
from bs4 import BeautifulSoup
from django.core.mail import EmailMultiAlternatives, SafeMIMEMultipart, SafeMIMEText
from django.utils import translation

from pretix.base.models import OrderPayment

from pretix_cz_banktransfer.reference import get_or_create_reference
from pretix_cz_banktransfer.signals import add_qr_code_to_payment_mail


def _settings(event):
    event.settings.payment_czbanktransfer_domestic_account_number = "185141554"
    event.settings.payment_czbanktransfer_bank_code = "0300"
    event.settings.payment_czbanktransfer_iban = "CZ4903000000000185141554"


def _message(body, html=None):
    """
    Same shape mail_send_task builds: the HTML alternative is a
    multipart/related container whose first part is the HTML itself.
    """
    message = EmailMultiAlternatives(subject="Payment", body=body, to=["a@example.org"])
    if html is not None:
        related = SafeMIMEMultipart(_subtype="related", encoding=settings.DEFAULT_CHARSET)
        related.attach(SafeMIMEText(html, "html", settings.DEFAULT_CHARSET))
        message.attach_alternative(related, "multipart/related")
    return message


def _pending_payment(order):
    return order.payments.create(
        provider="czbanktransfer", amount=Decimal("1250.00"),
        state=OrderPayment.PAYMENT_STATE_PENDING,
    )


def _parts(message):
    return message.alternatives[0].content.get_payload()


@pytest.mark.django_db
def test_qr_is_embedded_next_to_the_payment_instructions(cz_env):
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("AAAAA")
    _pending_payment(order)
    vs = get_or_create_reference(order).variable_symbol

    message = add_qr_code_to_payment_mail(
        event,
        message=_message(
            body=f"Variable symbol: {vs}",
            html=f"<html><body><p>Account: 185141554/0300</p><p>Variable symbol: {vs}</p>"
                 f"<div>footer</div></body></html>",
        ),
        order=order,
    )

    parts = _parts(message)
    html = parts[0].get_payload(decode=True).decode(settings.DEFAULT_CHARSET)
    assert 'src="cid:czbanktransfer-qr"' in html
    # Directly after the block naming the variable symbol, not dumped at the end
    # under the footer.
    assert html.index("cid:czbanktransfer-qr") < html.index("footer")

    image = parts[1]
    assert image.get_content_type() == "image/png"
    assert image["Content-ID"] == "<czbanktransfer-qr>"
    assert image.get_payload(decode=True)[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.django_db
def test_caption_and_alt_text_do_not_repeat_each_other(cz_env):
    """
    A client that blocks images falls back to the alt text, so a caption and an
    alt saying the same thing read as the sentence twice over.
    """
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("FFFFF")
    _pending_payment(order)
    vs = get_or_create_reference(order).variable_symbol

    message = add_qr_code_to_payment_mail(
        event,
        message=_message(body=f"Variable symbol: {vs}", html=f"<html><body><p>{vs}</p></body></html>"),
        order=order,
    )
    html = _parts(message)[0].get_payload(decode=True).decode(settings.DEFAULT_CHARSET)
    soup = BeautifulSoup(html, "lxml")
    img = soup.find("img")
    caption = img.parent.get_text().replace(img.get("alt", ""), "").strip()
    assert caption
    assert img["alt"] != caption


@pytest.mark.django_db
def test_caption_follows_the_customers_language(cz_env):
    """
    email_filter is not sent inside a language() context, so without asking for
    the order's locale explicitly the caption comes out in whatever language the
    worker happens to be in while the rest of the mail is Czech.
    """
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("GGGGG")
    order.locale = "cs"
    order.save()
    _pending_payment(order)
    vs = get_or_create_reference(order).variable_symbol

    with translation.override("en"):
        message = add_qr_code_to_payment_mail(
            event,
            message=_message(body=f"Variable symbol: {vs}", html=f"<html><body><p>{vs}</p></body></html>"),
            order=order,
        )
    html = _parts(message)[0].get_payload(decode=True).decode(settings.DEFAULT_CHARSET)
    assert "Naskenujte" in html
    assert "Scan to pay" not in html


@pytest.mark.django_db
def test_mails_that_are_not_payment_instructions_are_left_alone(cz_env):
    """
    Every mail for the order passes through this filter - only the one actually
    carrying the instructions should grow a QR code.
    """
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("BBBBB")
    _pending_payment(order)

    message = add_qr_code_to_payment_mail(
        event,
        message=_message(body="Your seats have changed.", html="<html><body><p>Hi</p></body></html>"),
        order=order,
    )
    assert len(_parts(message)) == 1
    assert "cid:czbanktransfer-qr" not in _parts(message)[0].get_payload(decode=True).decode()


@pytest.mark.django_db
def test_order_without_a_waiting_transfer_is_left_alone(cz_env):
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("CCCCC")
    payment = _pending_payment(order)
    vs = get_or_create_reference(order).variable_symbol
    payment.state = OrderPayment.PAYMENT_STATE_CONFIRMED
    payment.save()

    message = add_qr_code_to_payment_mail(
        event,
        message=_message(body=f"Variable symbol: {vs}", html=f"<html><body><p>{vs}</p></body></html>"),
        order=order,
    )
    assert len(_parts(message)) == 1


@pytest.mark.django_db
def test_plain_text_mail_gets_the_code_as_a_file(cz_env):
    """
    An event sending plain-text-only mail has no HTML part to embed into - the
    customer should still end up with the code rather than nothing.
    """
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("DDDDD")
    _pending_payment(order)
    vs = get_or_create_reference(order).variable_symbol

    message = add_qr_code_to_payment_mail(
        event, message=_message(body=f"Variable symbol: {vs}"), order=order,
    )
    assert [a[0] for a in message.attachments] == ["qr-platba.png"]


@pytest.mark.django_db
def test_a_broken_qr_never_costs_the_customer_their_instructions(cz_env, monkeypatch):
    organizer, event, make_order = cz_env
    _settings(event)
    order = make_order("EEEEE")
    _pending_payment(order)
    vs = get_or_create_reference(order).variable_symbol

    def boom(payload, **kwargs):
        raise RuntimeError("no qr today")

    monkeypatch.setattr("pretix_cz_banktransfer.signals.spd_qr_png", boom)
    body = f"Variable symbol: {vs}"
    message = add_qr_code_to_payment_mail(
        event, message=_message(body=body, html=f"<html><body><p>{vs}</p></body></html>"), order=order,
    )
    assert message.body == body
    assert len(_parts(message)) == 1


@pytest.mark.django_db
def test_mail_without_an_order_is_left_alone(cz_env):
    organizer, event, make_order = cz_env
    message = add_qr_code_to_payment_mail(event, message=_message(body="Hello"), order=None)
    assert message.attachments == []
