from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from pretix.base.models import Organizer
from pretix.control.permissions import OrganizerPermissionRequiredMixin
from pretix.control.views.organizer import OrganizerDetailViewMixin
from pretix.helpers.http import redirect_to_url

from .forms import CzechBankTransferOrganizerSettingsForm


class CzechBankTransferOrganizerSettingsView(
    OrganizerDetailViewMixin, OrganizerPermissionRequiredMixin, FormView
):
    model = Organizer
    permission = "organizer.settings.general:write"
    form_class = CzechBankTransferOrganizerSettingsForm
    template_name = "pretix_cz_banktransfer/organizer_settings.html"

    def get_success_url(self):
        return reverse(
            "plugins:pretix_cz_banktransfer:settings",
            kwargs={"organizer": self.request.organizer.slug},
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["obj"] = self.request.organizer
        return kwargs

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save()
            if form.has_changed():
                self.request.organizer.log_action(
                    "pretix.organizer.settings",
                    user=self.request.user,
                    data={key: form.cleaned_data.get(key) for key in form.changed_data},
                )
            messages.success(self.request, _("Your changes have been saved."))
            return redirect_to_url(self.get_success_url())

        messages.error(self.request, _("We could not save your changes. See below for details."))
        return self.form_invalid(form)
