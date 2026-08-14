from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = [("pretixbase", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="CzechBankTransferCounter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("next_value", models.PositiveBigIntegerField(default=1)),
                ("organizer", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="czbanktransfer_counter", to="pretixbase.organizer")),
            ],
        ),
        migrations.CreateModel(
            name="CzechBankTransferReference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variable_symbol", models.CharField(max_length=10, validators=[django.core.validators.RegexValidator("^\\d{1,10}$")])),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="czbanktransfer_reference", to="pretixbase.order")),
                ("organizer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="czbanktransfer_references", to="pretixbase.organizer")),
            ],
        ),
        migrations.AddConstraint(
            model_name="czechbanktransferreference",
            constraint=models.UniqueConstraint(fields=("organizer", "variable_symbol"), name="czbanktransfer_unique_vs_per_organizer"),
        ),
    ]
