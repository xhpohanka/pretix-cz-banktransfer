from django.db import IntegrityError, transaction

from .models import CzechBankTransferCounter, CzechBankTransferReference


def get_or_create_reference(order, prefix=""):
    if prefix and (not prefix.isdigit() or len(prefix) > 6):
        raise ValueError("Variable symbol prefix must contain at most six digits.")
    try:
        return CzechBankTransferReference.objects.get(order=order)
    except CzechBankTransferReference.DoesNotExist:
        pass

    organizer = order.event.organizer
    with transaction.atomic():
        # Locking the organizer serializes both first-time counter creation and allocation.
        organizer.__class__.objects.select_for_update().get(pk=organizer.pk)
        existing = CzechBankTransferReference.objects.filter(order=order).first()
        if existing:
            return existing
        counter, _ = CzechBankTransferCounter.objects.select_for_update().get_or_create(
            organizer=organizer
        )
        max_counter_value = 10 ** (10 - len(prefix)) - 1
        while counter.next_value <= max_counter_value:
            value = counter.next_value
            counter.next_value += 1
            counter.save(update_fields=("next_value",))
            try:
                with transaction.atomic():
                    return CzechBankTransferReference.objects.create(
                        order=order, organizer=organizer,
                        variable_symbol=f"{prefix}{value}",
                    )
            except IntegrityError:
                # Explicitly skip a value that was inserted manually or by a prior allocator.
                continue
    raise RuntimeError("The variable symbol range for this prefix is exhausted.")
