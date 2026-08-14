from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from pretix.base.models import Event, Item, Order, OrderPosition, Organizer, Quota


@pytest.fixture
def cz_env():
    organizer = Organizer.objects.create(
        name="Czech Organizer", slug="czech-organizer",
        plugins="pretix.plugins.banktransfer,pretix_cz_banktransfer",
    )
    event = Event.objects.create(
        organizer=organizer, name="Czech Event", slug="czech-event", currency="CZK",
        date_from=now(), plugins="pretix.plugins.banktransfer,pretix_cz_banktransfer",
    )
    quota = Quota.objects.create(event=event, name="Tickets", size=None)
    item = Item.objects.create(event=event, name="Ticket", default_price="1250.00")
    quota.items.add(item)

    def make_order(code):
        with scope(organizer=organizer):
            order = Order.objects.create(
                event=event, code=code, status=Order.STATUS_PENDING, total="1250.00",
                datetime=now(), expires=now() + timedelta(days=10),
                sales_channel=organizer.sales_channels.get(identifier="web"),
            )
            OrderPosition.objects.create(order=order, item=item, variation=None, price="1250.00")
        return order

    with scope(organizer=organizer):
        yield organizer, event, make_order
