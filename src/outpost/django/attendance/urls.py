from django.urls import include, re_path

from . import views

app_name = "attendance"

urlpatterns = [
    re_path(
        r"^(?P<terminal_id>\d+)/(?P<card_id>[\dA-F]{8})/$",
        views.ClockView.as_view(),
        name="input",
    )
]
