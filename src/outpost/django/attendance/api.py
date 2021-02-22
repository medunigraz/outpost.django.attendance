import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from outpost.django.api.permissions import ExtendedDjangoModelPermissions
from outpost.django.campusonline import models as co
from rest_flex_fields.views import FlexFieldsMixin
from rest_framework import exceptions, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.filters import DjangoObjectPermissionsFilter, OrderingFilter
from rest_framework.response import Response

from . import filters, models, serializers
from .permissions import ActiveCampusOnlineHoldingPermission

logger = logging.getLogger(__name__)


class TerminalViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.Terminal.objects.all()
    serializer_class = serializers.TerminalSerializer
    permission_classes = (ExtendedDjangoModelPermissions,)
    permit_list_expands = ("rooms",)


class CampusOnlineHoldingViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.CampusOnlineHolding.objects.all()
    serializer_class = serializers.CampusOnlineHoldingSerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = filters.CampusOnlineHoldingFilter
    ordering_fields = ("initiated",)
    permission_classes = (permissions.IsAuthenticated,)
    permit_list_expands = (
        "entries",
        "entries.student",
        "manual_entries",
        "manual_entries.student",
        "course_group_term",
        "accredited",
    )
    http_method_names = viewsets.ModelViewSet.http_method_names + [
        "start",
        "end",
        "cancel",
    ]

    def get_queryset(self):
        username = self.request.user.username
        return self.queryset.filter(
            lecturer__username=username, state__in=("pending", "running")
        )

    @action(methods=["start", "end", "cancel"], detail=True)
    def transition(self, request, pk=None):
        holding = self.get_object()
        getattr(holding, request.method.lower())()
        holding.save()
        data = self.serializer_class(holding).data
        return Response(data)


class CampusOnlineEntryViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.CampusOnlineEntry.objects.all()
    serializer_class = serializers.CampusOnlineEntrySerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = filters.CampusOnlineEntryFilter
    ordering_fields = ("initiated",)
    permission_classes = (
        permissions.IsAuthenticated,
        ActiveCampusOnlineHoldingPermission,
    )
    permit_list_expands = ("holding", "student")
    http_method_names = viewsets.ModelViewSet.http_method_names + ["discard"]

    def get_queryset(self):
        username = self.request.user.username
        return self.queryset.filter(
            holding__lecturer__username=username, holding__state="running"
        )

    @action(methods=["discard"], detail=True)
    def transition(self, request, pk=None):
        entry = self.get_object()
        getattr(entry, request.method.lower())()
        entry.save()
        data = self.serializer_class(entry).data
        return Response(data)


class ManualCampusOnlineEntryViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.ManualCampusOnlineEntry.objects.all()
    serializer_class = serializers.ManualCampusOnlineEntrySerializer
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = filters.ManualCampusOnlineEntryFilter
    ordering_fields = ("assigned",)
    permission_classes = (
        permissions.IsAuthenticated,
        ActiveCampusOnlineHoldingPermission,
    )
    permit_list_expands = ("holding", "student", "room")
    http_method_names = viewsets.ModelViewSet.http_method_names + ["discard", "leave"]

    def get_queryset(self):
        username = self.request.user.username
        return self.queryset.filter(
            holding__lecturer__username=username, holding__state="running"
        )

    @action(methods=["discard", "leave"], detail=True)
    def transition(self, request, pk=None):
        entry = self.get_object()
        getattr(entry, request.method.lower())()
        entry.save()
        data = self.serializer_class(entry).data
        return Response(data)


class StatisticsViewSet(viewsets.ModelViewSet):
    queryset = models.Statistics.objects.all()
    serializer_class = serializers.StatisticsSerializer
    permission_classes = (ExtendedDjangoModelPermissions,)
    filter_backends = (DjangoObjectPermissionsFilter,)

    # def get_queryset(self):
    #    return get_objects_for_user(
    #        self.request.user,
    #        'attendance.view_statistics',
    #        klass=self.queryset.model
    #    )
