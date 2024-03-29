import logging

from django.utils.translation import gettext as _
from outpost.django.campusonline import models as co
from rest_framework import authentication, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from outpost.django.campusonline.serializers import AuthenticatedStudentSerializer
from . import models, serializers

logger = logging.getLogger(__name__)


class ClockView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, terminal_id, card_id, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        logger.debug(f"Incoming request for terminal {terminal_id}")
        try:
            self.terminal = models.Terminal.objects.get(
                pk=terminal_id, online=True, enabled=True
            )
        except models.Terminal.DoesNotExist:
            logger.warn(f"Unknown terminal {terminal_id}")
            raise NotFound(_("Unknown terminal identification"))
        try:
            self.student = co.Student.objects.get(cardid=card_id)
        except co.Student.DoesNotExist:
            logger.warn(f"No student found for cardid {card_id}")
            raise NotFound(_("Unknown student identification"))

    def get(self, request, **kwargs):
        logger.debug(f"Preflight request for {self.terminal}:{self.student}")
        try:
            data = self.terminal.plugins.hook.preflight(
                terminal=self.terminal, student=self.student
            )
        except Exception as e:
            return Response(str(e), status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "terminal": serializers.TerminalSerializer(self.terminal).data,
                "student": AuthenticatedStudentSerializer(self.student).data,
                "cardid": self.student.cardid,
                "data": [entry for entry in data if entry],
            }
        )

    def post(self, request, **kwargs):
        logger.debug(f"Clock request for {self.terminal}:{self.student}")
        entry = models.Entry.objects.create(
            student=self.student, terminal=self.terminal
        )
        data = self.terminal.plugins.hook.clock(entry=entry, payload=request.data)
        return Response(
            {
                "terminal": serializers.TerminalSerializer(self.terminal).data,
                "student": AuthenticatedStudentSerializer(self.student).data,
                "cardid": self.student.cardid,
                "entry": entry.pk,
                "data": [entry for entry in data if entry],
            }
        )
