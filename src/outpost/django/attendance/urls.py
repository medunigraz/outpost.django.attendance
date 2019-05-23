from django.conf.urls import include, url

from . import views

urlpatterns = [url(r"^(?P<room>[\w\d\.]+)/$", views.HoldingView.as_view())]
