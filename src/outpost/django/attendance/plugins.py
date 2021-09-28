import logging
from typing import List

import pluggy
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.translation import gettext as _
from outpost.django.base.plugins import Plugin
from rest_framework.exceptions import NotFound

logger = logging.getLogger(__name__)


class TerminalBehaviourPlugin(Plugin):
    pass


class TerminalBehaviour(object):

    name = f"{__name__}.TerminalBehaviour"
    base = TerminalBehaviourPlugin
    hookspec = pluggy.HookspecMarker(name)
    hookimpl = pluggy.HookimplMarker(name)

    @classmethod
    def manager(cls, condition=lambda _: True):
        pm = pluggy.PluginManager(cls.name)
        pm.add_hookspecs(cls)
        for plugin in cls.base.all():
            if condition(plugin):
                logger.info(f"Registering plugin: {plugin}")
                pm.register(plugin())
        return pm

    @hookspec
    def preflight(self, terminal, student) -> List[dict]:
        """
        """

    @hookspec
    def clock(self, entry, payload) -> List[str]:
        """
        """


class DebugTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("Debugger")

    @TerminalBehaviour.hookimpl
    def preflight(self, terminal, student):
        logger.debug(f"{self.__class__.__name__}: preflight({terminal}, {student})")
        return {"id": f"{self.__class__.__name__}:preflight"}

    @TerminalBehaviour.hookimpl
    def clock(self, entry, payload):
        logger.debug(f"{self.__class__.__name__}: clock({entry}, {payload})")
        return {"id": f"{self.__class__.__name__}:clock"}


class CampusOnlineTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("CAMPUSonline")

    @TerminalBehaviour.hookimpl
    def preflight(self, terminal, student):
        from .models import CampusOnlineEntry

        # import pudb ; pu.db
        if terminal.rooms.count() < 2:
            return
        try:
            coe = CampusOnlineEntry.objects.get(
                incoming__student=student, ended__isnull=True
            )
            logger.debug(f"Outgoing clock in: {coe}")
            return
        except CampusOnlineEntry.DoesNotExist:
            pass
        return {
            "id": f"{self.__class__.__name__}:room",
            "question": _("Please select room"),
            "options": {r.pk: str(r) for r in terminal.rooms.all()},
        }

    @TerminalBehaviour.hookimpl
    def clock(self, entry, payload):
        from .models import CampusOnlineHolding, CampusOnlineEntry

        # import pudb ; pu.db
        logger.debug(f"{self.__class__.__name__}: create({entry})")
        try:
            coe = CampusOnlineEntry.objects.get(
                incoming__student=entry.student, ended__isnull=True
            )
            # Existing entry, student leaving room
            logger.debug(f"Student {entry.student} leaving {coe.room}")
            if not coe.holding:
                # No holding but prior entry found, assume he/she left the room
                # with this entry
                logger.debug(f"{entry.student} canceling {coe.room}")
                coe.cancel(entry)
                msg = _("Goodbye")
            else:
                try:
                    # Holding is present and student should be assigned to it
                    if coe.holding.state == "running" and coe.state == "assigned":
                        logger.debug(f"{entry.student} leaving {coe.room}")
                        coe.leave(entry)
                    msg = _(
                        f"Thank you for attending {coe.holding.course_group_term.coursegroup}"
                    )
                except ObjectDoesNotExist as e:
                    logger.warn(f"Inconsitent holding found for entry {coe}: {e}")
                    msg = _("Goodbye")
        except CampusOnlineEntry.DoesNotExist:
            # New entry, student entering the room
            room_count = entry.terminal.rooms.count()
            if room_count == 0:
                logger.warn(
                    f"Terminal {entry.incoming.terminal} has no rooms assigned."
                )
                raise NotFound(_(f"Terminal has no suitable rooms assigned."))
            elif room_count == 1:
                room = entry.terminal.rooms.first()
            else:
                room_id = payload.get(f"{self.__class__.__name__}:room")
                try:
                    room = entry.terminal.rooms.get(pk=room_id)
                except entry.terminal.rooms.model.DoesNotExist:
                    logger.warn(
                        f"Terminal {entry.incoming.terminal} has no room with PK {room_id} assigned."
                    )
                    raise NotFound(_(f"No such room found for terminal."))
            coe = CampusOnlineEntry.objects.create(incoming=entry, room=room)
            logger.debug(f"Student {entry.student} entering {room}")
            holdings = CampusOnlineHolding.objects.filter(
                room=room, initiated__lte=timezone.now(), state="running"
            )
            if holdings.count() > 0:
                for holding in holdings:
                    if (
                        entry.student
                        in holding.course_group_term.coursegroup.students.all()
                    ):
                        coe.assign(holding)
                        break
                else:
                    # TODO: Find a better way to handle unoffical attendants
                    # with multiple parallel holdings. Right now it assigns to
                    # the first holding from all parallel ones.
                    coe.assign(holdings.first())
                msg = _(
                    f"Welcome {coe.incoming.student.display} to {coe.holding.course_group_term.coursegroup}"
                )
            else:
                logger.debug(f"No active holding found for {coe}")
                msg = _("Welcome {coe.incoming.student.display}")
        coe.save()
        return msg.format(coe=coe)


class StatisticsTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("Statistics")

    @TerminalBehaviour.hookimpl
    def clock(self, entry, payload):
        from .models import StatisticsEntry

        logger.debug(f"{self.__class__.__name__}: create({entry})")
        msg = list()
        for s in entry.terminal.statistics_set.all():
            try:
                se = StatisticsEntry.objects.filter(
                    statistics=s,
                    incoming__student=entry.student,
                    outgoing=None,
                    state="created",
                ).latest()
                se.complete(entry)
                se.save()

                msg.append(_("Recorded: {statistic}").format(statistic=s))
            except StatisticsEntry.DoesNotExist:
                se = StatisticsEntry.objects.create(statistics=s, incoming=entry)
                msg.append(_("Concluded: {statistic}").format(statistic=s))
        return msg


class ImmunizationTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("Immunization")

    @TerminalBehaviour.hookimpl
    def preflight(self, terminal, student):
        if not student.immunized:
            raise Exception(_("Not Immunized!"))

    @TerminalBehaviour.hookimpl
    def clock(self, entry, payload):
        return _("Immunized!")
