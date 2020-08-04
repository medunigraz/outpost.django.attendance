from django.conf.urls import include, url

from . import views

app_name = "attendance"

urlpatterns = [
    url(
        r"^(?P<terminal_id>\d+)/(?P<card_id>[\dA-F]{8})/$",
        views.ClockView.as_view(),
        name="input",
    )
]
