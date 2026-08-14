from django.urls import path

from .views import CzechBankTransferOrganizerSettingsView


urlpatterns = [
    path(
        "control/organizer/<str:organizer>/cz-banktransfer/",
        CzechBankTransferOrganizerSettingsView.as_view(),
        name="settings",
    ),
]
