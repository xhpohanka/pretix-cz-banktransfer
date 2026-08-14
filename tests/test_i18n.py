from django.utils.translation import gettext, override


def test_czech_translation_is_shipped():
    with override("cs"):
        assert gettext("Variable symbol") == "Variabilní symbol"
        assert gettext("Domestic account number") == "Tuzemské číslo účtu"
        assert gettext("Enable Czech bank transfer by default") == "Ve výchozím nastavení povolit český bankovní převod"
