from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission

from . import models


class ActiveCampusOnlineHoldingPermission(BasePermission):
    message = _("No active holdings found for this user.")

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # Find out if user has an active holding right now and see if the room
        # matches.
        holdings = models.CampusOnlineHolding.objects.filter(
            state="running",
            initiated__lte=timezone.now(),
            lecturer__username=request.user.username,
        ).exists()
        return holdings
