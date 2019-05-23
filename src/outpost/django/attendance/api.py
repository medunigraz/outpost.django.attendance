import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from rest_flex_fields.views import FlexFieldsMixin
from rest_framework import (
    exceptions,
    permissions,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.filters import (
    DjangoObjectPermissionsFilter,
    OrderingFilter,
)
from rest_framework.response import Response

from outpost.django.api.permissions import ExtendedDjangoModelPermissions
from outpost.django.campusonline import models as co

from . import (
    filters,
    models,
    serializers,
)

logger = logging.getLogger(__name__)


class TerminalViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.Terminal.objects.all()
    serializer_class = serializers.TerminalSerializer
    permission_classes = (
        ExtendedDjangoModelPermissions,
    )
    permit_list_expands = (
        'rooms',
    )


class ClockViewSet(viewsets.ViewSet):
    permission_classes = (
        permissions.IsAuthenticated,
    )

    def create(self, request):
        terminal_id = request.data.get('terminal')
        logger.debug(f'Incoming request for terminal {terminal_id}')
        try:
            terminal = models.Terminal.objects.get(
                pk=terminal_id,
                online=True,
                enabled=True
            )
        except models.Terminal.DoesNotExist:
            logger.warn(f'Unknown terminal {terminal_id}')
            raise exceptions.NotFound('Unknown terminal identification')
        room_id = request.data.get('room')
        try:
            room = terminal.rooms.get(
                pk=room_id
            )
        except terminal.rooms.DoesNotExist:
            logger.warn(f'Unknown room {room_id}')
            raise exceptions.NotFound('Unknown room identification')
        card_id = request.data.get('cardid', None)
        if not card_id:
            logger.warn(f'Missing card id')
            raise exceptions.ValidationError('Missing card information')
        try:
            student = co.Student.objects.get(cardid=card_id)
        except co.Student.DoesNotExist:
            logger.warn(f'No student found for cardid {card_id}')
            raise exceptions.NotFound('Unknown student identification')
        entry = models.Entry.objects.create(
            student=student,
            terminal=terminal,
            room=room
        )
        return Response({
            'status': entry.status,
            'name': str(student),
            'entry': entry.pk,
            'room': room
        })


class CampusOnlineHoldingViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.CampusOnlineHolding.objects.all()
    serializer_class = serializers.CampusOnlineHoldingSerializer
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filter_class = filters.CampusOnlineHoldingFilter
    ordering_fields = (
        'initiated',
    )
    permission_classes = (
        permissions.IsAuthenticated,
    )
    permit_list_expands = (
        'entries',
    )
    http_method_names = viewsets.ModelViewSet.http_method_names + [
        'start', 'end', 'cancel'
    ]

    def get_queryset(self):
        username = self.request.user.username
        return self.queryset.filter(
            lecturer__username=username,
            state__in=(
                'pending',
                'running'
            )
        )

    @action(methods=['start', 'end', 'cancel'], detail=True)
    def transition(self, request, pk=None):
        holding = self.get_object()
        getattr(holding, request.method.lower())()
        holding.save()
        data = self.serializer_class(holding).data
        return Response(data)


class CampusOnlineEntryViewSet(FlexFieldsMixin, viewsets.ModelViewSet):
    queryset = models.CampusOnlineEntry.objects.all()
    serializer_class = serializers.CampusOnlineEntrySerializer
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
    )
    filter_class = filters.CampusOnlineEntryFilter
    ordering_fields = (
        'initiated',
    )
    permission_classes = (
        permissions.IsAuthenticated,
    )
    permit_list_expands = (
        'holding',
        'student',
    )
    http_method_names = viewsets.ModelViewSet.http_method_names + [
        'discard'
    ]

    def get_queryset(self):
        username = self.request.user.username
        return self.queryset.filter(
            holding__lecturer__username=username,
            holding__state='running'
        )

    @action(methods=['discard'], detail=True)
    def transition(self, request, pk=None):
        entry = self.get_object()
        getattr(entry, request.method.lower())()
        entry.save()
        data = self.serializer_class(entry).data
        return Response(data)


class StatisticsViewSet(viewsets.ModelViewSet):
    queryset = models.Statistics.objects.all()
    serializer_class = serializers.StatisticsSerializer
    permission_classes = (
        ExtendedDjangoModelPermissions,
    )
    filter_backends = (
        DjangoObjectPermissionsFilter,
    )

    #def get_queryset(self):
    #    return get_objects_for_user(
    #        self.request.user,
    #        'attendance.view_statistics',
    #        klass=self.queryset.model
    #    )
