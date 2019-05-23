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
                pm.register(plugin())
        return pm

    @hookspec
    def create(self, entry) -> List[str]:
        """
        """

    @hookspec
    def update(self, entry) -> List[str]:
        """
        """


class DebugTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("Debugger")

    @TerminalBehaviour.hookimpl
    def create(self, entry):
        logger.debug(f"{self.__class__.__name__}: create({entry})")

    @TerminalBehaviour.hookimpl
    def update(self, entry):
        logger.debug(f"{self.__class__.__name__}: update({entry})")


class CampusOnlineTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("CAMPUSonline")

    @TerminalBehaviour.hookimpl
    def create(self, entry):
        from .models import CampusOnlineHolding, CampusOnlineEntry

        logger.debug(f"{self.__class__.__name__}: create({entry})")
        coe, created = CampusOnlineEntry.objects.get_or_create(
            incoming__student=entry.student,
            incoming__room=entry.room,
            ended__isnull=True,
            defaults={"incoming": entry},
        )
        if created:
            # New entry, student entering the room
            logger.debug(f"Student {entry.student} entering {entry.room}")
            try:
                holding = CampusOnlineHolding.objects.get(
                    room=entry.room, initiated__lte=timezone.now(), state="running"
                )
                coe.assign(holding)
                msg = _(
                    "Welcome {coe.incoming.student.display} to "
                    "{coe.holding.course_group_term.coursegroup}"
                )
            except CampusOnlineHolding.DoesNotExist:
                logger.debug(f"No active holding found for {coe}")
                msg = _("Welcome {coe.incoming.student.display}")
        else:
            # Existing entry, student leaving room
            logger.debug(f"Student {entry.student} leaving {entry.room}")
            if not coe.holding:
                # No holding but prior entry found, assume he/she left the room
                # with this entry
                logger.debug(f"{entry.student} canceling {entry.room}")
                coe.cancel(entry)
                msg = _("Goodbye")
            else:
                # Holding is present and student should be assigned to it
                if coe.holding.state == "running" and coe.state == "assigned":
                    logger.debug(f"{entry.student} leaving {entry.room}")
                    coe.leave(entry)
                msg = _(
                    "Thank you for attending "
                    "{coe.holding.course_group_term.coursegroup}"
                )
        coe.save()
        return msg.format(coe=coe)


class StatisticsTerminalBehaviour(TerminalBehaviourPlugin):

    name = _("Statistics")

    @TerminalBehaviour.hookimpl
    def create(self, entry):
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
