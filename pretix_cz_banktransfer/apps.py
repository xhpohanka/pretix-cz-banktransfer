from django.utils.translation import gettext_lazy as _

from pretix.base.plugins import PLUGIN_LEVEL_EVENT_ORGANIZER_HYBRID, PluginConfig

from . import __version__


class PluginApp(PluginConfig):
    name = "pretix_cz_banktransfer"
    verbose_name = "Bankovní převod (CZ)"

    class PretixPluginMeta:
        name = _("Czech bank transfer")
        author = "Jan Pohanka"
        description = _("Accept CZK payments to a Czech bank account with a variable symbol and QR Platba.")
        category = "PAYMENT"
        visible = True
        version = __version__
        compatibility = "pretix>=2026.6.0.dev0"
        level = PLUGIN_LEVEL_EVENT_ORGANIZER_HYBRID
        settings_links = [
            ((_('Payment'), _('Czech bank transfer')), 'control:event.settings.payment.provider', {'provider': 'czbanktransfer'}),
        ]

    def ready(self):
        from . import signals  # noqa
