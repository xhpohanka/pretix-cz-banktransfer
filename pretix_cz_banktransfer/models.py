from django.core.validators import RegexValidator
from django.db import models


class CzechBankTransferCounter(models.Model):
    organizer = models.OneToOneField(
        "pretixbase.Organizer", on_delete=models.CASCADE, related_name="czbanktransfer_counter"
    )
    next_value = models.PositiveBigIntegerField(default=1)


class CzechBankTransferReference(models.Model):
    order = models.OneToOneField(
        "pretixbase.Order", on_delete=models.CASCADE, related_name="czbanktransfer_reference"
    )
    organizer = models.ForeignKey(
        "pretixbase.Organizer", on_delete=models.CASCADE, related_name="czbanktransfer_references"
    )
    variable_symbol = models.CharField(
        max_length=10,
        validators=[RegexValidator(r"^\d{1,10}$")],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organizer", "variable_symbol"), name="czbanktransfer_unique_vs_per_organizer"
            )
        ]
