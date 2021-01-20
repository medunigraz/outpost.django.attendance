import logging
from datetime import timedelta
from itertools import chain

import django
from django.contrib.postgres.fields import DateTimeRangeField, JSONField
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField, transition
from model_utils.models import TimeStampedModel
from outpost.django.base.decorators import signal_connect
from outpost.django.base.fields import ChoiceArrayField
from outpost.django.base.models import NetworkedDeviceMixin, RelatedManager
from outpost.django.campusonline.models import CourseGroupTerm

from .conf import settings
from .tasks import EmailExternalsTask
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
        # Find COHs in the current room, that are not parallel holdings and end
        # them. Parallel holdings are left running if there are any.
        cohs = CampusOnlineHolding.objects.filter(
            room=self.room, state="running"
        ).exclude(
            Q(pk=self.pk)
            | Q(course_group_term__pk=self.course_group_term.pk)
            | (
                Q(course_group_term__room=self.course_group_term.room)
                & Q(course_group_term__start=self.course_group_term.start)
                & Q(course_group_term__end=self.course_group_term.end)
            )
        )
        for coh in cohs:
            logger.info(f"Ending holding {coh} because of new one")
            coh.end()
            coh.save()
        parallel = CourseGroupTerm.objects.filter(
            room=self.course_group_term.room,
            start=self.course_group_term.start,
            end=self.course_group_term.end,
        ).exclude(pk=self.course_group_term.pk)
        parallel_students = list(
            chain(*[c.coursegroup.students.all() for c in parallel])
        )
        coes = CampusOnlineEntry.objects.filter(
            room=self.room, holding=None, state="created"
        )
        for coe in coes:
            # If there are parallel holdins, check if student is in a group
            # other than the one started right now.
            if parallel.exists():
                if coe.incoming.student in parallel_students:
                    # Student is officially part of another holding, skip them.
                    # If a holding is started for their group, they will be
                    # picked up then.
                    continue
            logger.debug(f"Assigning {coe} to {self}")
            coe.assign(self)
            coe.save()

    @transition(field=state, source="running", target="finished")
    def end(self, finished=None):
        logger.info(f"Ending holding {self}")
        self.finished = finished or timezone.now()
        for coe in self.entries.filter(state__in=("assigned", "left")):
            coe.complete(finished=self.finished)
            coe.save()
        for mcoe in self.manual_entries.filter(state__in=("assigned", "left")):
            mcoe.complete(finished=self.finished)
            mcoe.save()
        EmailExternalsTask().delay(self.pk)

    @transition(field=state, source=("running", "pending"), target="canceled")
    def cancel(self):
        logger.info(f"Canceling holding {self}")
        for coe in self.entries.filter(state__in=("assigned", "left")):
            coe.pullout()
            coe.save()
        for coe in self.manual_entries.filter(state__in=("assigned", "left")):
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
    accredited = models.BooleanField(default=False)

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
        self.accredited = self.holding.course_group_term.coursegroup.students.filter(
            pk=self.incoming.student.pk
        ).exists()
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
        from django.db import connection

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
        logger.debug(f"{self} completing")
        if self.state == "assigned":
            self.ended = finished or timezone.now()
        if entry:
            self.outgoing = entry
        data = [
            self.id,
            self.incoming.student.id,
            self.holding.course_group_term.coursegroup.id,
            self.holding.course_group_term.term,
            self.assigned,
            self.ended,
        ]
        logger.debug(f"{self} writing to CAMPUSonline")
        with connection.cursor() as cursor:
            cursor.execute(query, data)
        continuation = (
            CourseGroupTerm.objects.filter(
                room=self.room,
                coursegroup__students=self.incoming.student,
                start__gt=self.holding.course_group_term.end,
                start__lt=self.holding.course_group_term.end
                + settings.ATTENDANCE_CONTINUATION_BUFFER,
            )
            .order_by("start")
            .first()
        )
        if continuation:
            logger.debug(f"Creating continuation for {self}")
            self.objects.create(incoming=self.incoming, room=self.room)


@signal_connect
class ManualCampusOnlineEntry(models.Model):
    assigned = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    ended = models.DateTimeField(null=True, blank=True)
    holding = models.ForeignKey(
        "CampusOnlineHolding", models.CASCADE, related_name="manual_entries"
    )
    student = models.ForeignKey(
        "campusonline.Student", models.DO_NOTHING, db_constraint=False, related_name="+"
    )
    room = models.ForeignKey(
        "campusonline.Room", models.DO_NOTHING, db_constraint=False, related_name="+"
    )
    state = FSMField(default="assigned")
    accredited = models.BooleanField(default=False)

    class Meta:
        ordering = ("assigned", "ended")
        permissions = (
            (("view_manualcampusonlineentry", _("View manual CAMPUSonline Entry")),)
            if django.VERSION < (2, 1)
            else tuple()
        )

    def __str__(s):
        return f"{s.student} ({s.assigned}): {s.state}"

    def pre_save(self, *args, **kwargs):
        if self.pk:
            return
        # Fetch previous entries for the same student in the same holding and
        # mark them as 'leave' if they are assigned again.
        previous = ManualCampusOnlineEntry.objects.filter(
            student=self.student, holding=self.holding, state="assigned"
        )
        for p in previous:
            p.leave()
            p.save()
        # Check if student is officially part of this holdings course group and
        # mark them as accredited if this is the case.
        self.accredited = self.holding.course_group_term.coursegroup.students.filter(
            pk=self.student.pk
        ).exists()

    @transition(field=state, source=("assigned", "left"), target="canceled")
    def discard(self):
        logger.debug(f"Discarding {self}")
        self.assigned = None
        self.ended = timezone.now()

    @transition(field=state, source="assigned", target="left")
    def leave(self):
        logger.debug(f"{self} leaving")
        self.ended = timezone.now()

    @transition(field=state, source=("assigned", "left"), target="complete")
    def complete(self, finished=None):
        from django.db import connection

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
        logger.debug(f"{self} completing")
        if self.state == "assigned":
            self.ended = finished or timezone.now()
        data = [
            self.id,
            self.student.id,
            self.holding.course_group_term.coursegroup.id,
            self.holding.course_group_term.term,
            self.assigned,
            self.ended,
        ]
        logger.debug(f"{self} writing to CAMPUSonline")
        with connection.cursor() as cursor:
            cursor.execute(query, data)


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
