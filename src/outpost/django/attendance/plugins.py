import logging
from typing import List

import pluggy
from django.utils import timezone
from django.utils.translation import gettext as _

from outpost.django.base.plugins import Plugin

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
        room_count = entry.terminal.rooms.count()
        if room_count == 0:
            logger.warn(f"Terminal {entry.incoming.terminal} has no rooms assigned!")
            return
        elif room_count == 1:
            room = entry.terminal.rooms.first()
        else:
            room = entry.terminal.rooms.get(pk=payload.get("room"))
        coe, created = CampusOnlineEntry.objects.get_or_create(
            incoming__student=entry.student,
            ended__isnull=True,
            defaults={"incoming": entry, "room": room},
        )
        if created:
            # New entry, student entering the room
            logger.debug(f"Student {entry.student} entering {room}")
            try:
                holding = CampusOnlineHolding.objects.get(
                    room=room, initiated__lte=timezone.now(), state="running"
                )
                coe.assign(holding)
                msg = _(
                    f"Welcome {coe.incoming.student.display} to {coe.holding.course_group_term.coursegroup}"
                )
            except CampusOnlineHolding.DoesNotExist:
                logger.debug(f"No active holding found for {coe}")
                msg = _("Welcome {coe.incoming.student.display}")
        else:
            # Existing entry, student leaving room
            logger.debug(f"Student {entry.student} leaving {room}")
            if not coe.holding:
                # No holding but prior entry found, assume he/she left the room
                # with this entry
                logger.debug(f"{entry.student} canceling {room}")
                coe.cancel(entry)
                msg = _("Goodbye")
            else:
                # Holding is present and student should be assigned to it
                if coe.holding.state == "running" and coe.state == "assigned":
                    logger.debug(f"{entry.student} leaving {room}")
                    coe.leave(entry)
                msg = _(
                    f"Thank you for attending {coe.holding.course_group_term.coursegroup}"
                )
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
