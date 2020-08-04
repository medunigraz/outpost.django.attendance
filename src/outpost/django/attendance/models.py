import logging

import django

from django.conf import settings
from django.contrib.postgres.fields import DateTimeRangeField, JSONField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField, transition
from model_utils.models import TimeStampedModel

from outpost.django.base.decorators import signal_connect
from outpost.django.base.fields import ChoiceArrayField
from outpost.django.base.models import NetworkedDeviceMixin, RelatedManager

from .plugins import TerminalBehaviour

logger = logging.getLogger(__name__)


class Terminal(NetworkedDeviceMixin, models.Model):
    rooms = models.ManyToManyField(
        "campusonline.Room", db_constraint=False, related_name="terminals"
    )
    config = JSONField(null=True)
    behaviour = ChoiceArrayField(
        base_field=models.CharField(
            max_length=256,
            choices=[
                (p.qualified(), p.name)
                for p in TerminalBehaviour.manager().get_plugins()
            ],
        ),
        default=list,
    )

    class Meta:
        ordering = ("id",)
        permissions = (
            (("view_terminal", _("View Terminal")),)
            if django.VERSION < (2, 1)
            else tuple()
        )

    @property
    def plugins(self):
        pm = TerminalBehaviour.manager(lambda p: p.qualified() in self.behaviour)
        return pm

    def __str__(self):
        return self.hostname


class Entry(models.Model):
    terminal = models.ForeignKey("Terminal", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    student = models.ForeignKey(
        "campusonline.Student",
        models.DO_NOTHING,
        db_constraint=False,
        related_name="attendance",
    )

    class Meta:
        get_latest_by = "created"
        permissions = (
            (("view_entry", _("View Entry")),) if django.VERSION < (2, 1) else tuple()
        )

    def __str__(s):
        return f"{s.student} [{s.created}: {s.terminal}]"


class CampusOnlineHolding(models.Model):
    state = FSMField(default="pending")
    course_group_term = models.ForeignKey(
        "campusonline.CourseGroupTerm",
        models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
    )
    room = models.ForeignKey(
        "campusonline.Room",
        models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
    )
    lecturer = models.ForeignKey(
        "campusonline.Person",
        models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
    )
    initiated = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)

    objects = RelatedManager(
        select=(
            "course_group_term",
            "course_group_term__coursegroup",
            "course_group_term__coursegroup__course",
            "course_group_term__room",
            "course_group_term__person",
            "lecturer",
            "room",
        )
    )

    class Meta:
        get_latest_by = "initiated"
        permissions = (
            (("view_campusonlineholding", _("View CAMPUSonline Holding")),)
            if django.VERSION < (2, 1)
            else tuple()
        )

    @transition(field=state, source="pending", target="running")
    def start(self):
        self.initiated = timezone.now()
        logger.info(f"Starting holding {self}")
        cohs = CampusOnlineHolding.objects.filter(
            room=self.room, state="running"
        ).exclude(pk=self.pk)
        for coh in cohs:
            logger.info(f"Ending holding {coh} because of new one")
            coh.end()
            coh.save()
        coes = CampusOnlineEntry.objects.filter(
            room=self.room, holding=None, state="created"
        )
        for coe in coes:
            logger.debug(f"Assigning {coe} to {self}")
            coe.assign(self)
            coe.save()

    @transition(field=state, source="running", target="finished")
    def end(self, finished=None):
        from django.db import connection

        coes = CampusOnlineEntry.objects.filter(
            holding=self, state__in=("assigned", "left")
        )
        self.finished = finished or timezone.now()
        query = """
        INSERT INTO campusonline.stud_lv_anw (
            buchung_nr,
            stud_nr,
            grp_nr,
            termin_nr,
            anm_begin,
            anm_ende
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            );
        """
        for coe in coes:
            if coe.state == "assigned":
                coe.complete(finished=finished)
                coe.save()
            logger.debug(f"{coe} ending")
            data = [
                coe.id,
                coe.incoming.student.id,
                coe.holding.course_group_term.coursegroup.id,
                coe.holding.course_group_term.term,
                coe.assigned,
                coe.ended,
            ]
            logger.debug(f"{coe} writing to CAMPUSonline")
            with connection.cursor() as cursor:
                cursor.execute(query, data)

    @transition(field=state, source=("running", "pending"), target="canceled")
    def cancel(self):
        query = {"holding": self, "state__in": ("assigned", "left")}
        for coe in CampusOnlineEntry.objects.filter(**query):
            coe.pullout()
            coe.save()

    def __str__(s):
        return f"{s.course_group_term} [{s.lecturer}, {s.room}: {s.state}]"


class CampusOnlineEntry(models.Model):
    incoming = models.ForeignKey(
        "Entry", models.CASCADE, related_name="campusonlineentry"
    )
    outgoing = models.ForeignKey(
        "Entry", models.CASCADE, null=True, blank=True, related_name="+"
    )
    assigned = models.DateTimeField(null=True, blank=True)
    ended = models.DateTimeField(null=True, blank=True)
    holding = models.ForeignKey(
        "CampusOnlineHolding",
        models.CASCADE,
        null=True,
        blank=True,
        related_name="entries",
    )
    room = models.ForeignKey(
        "campusonline.Room",
        models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
    )
    state = FSMField(default="created")

    class Meta:
        ordering = ("incoming__created", "assigned", "ended")
        permissions = (
            (("view_campusonlineentry", _("View CAMPUSonline Entry")),)
            if django.VERSION < (2, 1)
            else tuple()
        )

    def __str__(s):
        return f"{s.incoming}: {s.state}"

    @transition(field=state, source="created", target="canceled")
    def cancel(self, entry=None):
        logger.debug(f"Canceling {self}")
        self.ended = timezone.now()
        self.outgoing = entry

    @transition(field=state, source="created", target="assigned")
    def assign(self, holding):
        logger.debug(f"Assigning {self} to {holding}")
        self.holding = holding
        self.assigned = timezone.now()

    @transition(field=state, source=("assigned", "left"), target="canceled")
    def discard(self):
        logger.debug(f"Discarding {self}")
        self.assigned = None
        self.ended = timezone.now()

    @transition(field=state, source="assigned", target="left")
    def leave(self, entry=None):
        logger.debug(f"{self} leaving")
        self.ended = timezone.now()
        self.outgoing = entry

    @transition(field=state, source=("assigned", "left"), target="complete")
    def complete(self, entry=None, finished=None):
        logger.debug(f"{self} completing")
        self.ended = finished or timezone.now()
        if entry:
            self.outgoing = entry
        if False:
            CampusOnlineEntry.objects.create()


class Statistics(models.Model):
    name = models.CharField(max_length=256)
    active = DateTimeRangeField(null=True, blank=True)
    terminals = models.ManyToManyField("Terminal")

    class Meta:
        ordering = ("id",)
        permissions = (
            (("view_statistics", _("View Statistics")),)
            if django.VERSION < (2, 1)
            else tuple()
        )

    def __str__(s):
        return f"{s.name} ({s.terminals.count()} Terminals / {s.active})"


class StatisticsEntry(models.Model):
    statistics = models.ForeignKey("Statistics", models.CASCADE, related_name="entries")
    incoming = models.ForeignKey("Entry", models.CASCADE, related_name="+")
    outgoing = models.ForeignKey(
        "Entry", models.CASCADE, null=True, blank=True, related_name="+"
    )
    state = FSMField(default="created")

    class Meta:
        unique_together = (("statistics", "incoming"),)
        ordering = ("incoming__created",)
        get_latest_by = "incoming__created"

    @transition(field=state, source="created", target="completed")
    def complete(self, entry=None):
        self.outgoing = entry

    def __str__(s):
        return f"{s.statistics}: {s.incoming}/{s.outgoing}"
