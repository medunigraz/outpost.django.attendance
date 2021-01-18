import logging
from datetime import timedelta

from celery.task import PeriodicTask, Task
from celery.task.schedules import crontab
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.template.loader import render_to_string
from outpost.django.campusonline.models import CourseGroupTerm

from .conf import settings

logger = logging.getLogger(__name__)


class EmailExternalsTask(Task):
    def run(self, pk_coh, pks_coe, pks_mcoe):
        from .models import (
            CampusOnlineHolding,
            CampusOnlineEntry,
            ManualCampusOnlineEntry,
        )

        coh = CampusOnlineHolding.objects.get(pk=pk_coh)
        if pks_coe:
            coes = CampusOnlineEntry.objects.filter(pk__in=pks_coe)
        else:
            coes = CampusOnlineEntry.objects.empty()
        if pks_mcoe:
            mcoes = ManualCampusOnlineEntry.objects.filter(pk__in=pks_mcoe)
        else:
            mcoes = ManualCampusOnlineEntry.objects.empty()

        logger.info(f"Sending mail for {coh}")

        context = {"coh": coh, "coes": coes, "mcoes": mcoes}

        msg = EmailMultiAlternatives(
            _(f"External attendees for {coh.course_group_termi.coursegroup}"),
            render_to_string("attendance/mail/external_attendees.txt", context),
            settings.DEFAULT_FROM_EMAIL,
            [coh.course_group_term.person.email],
        )
        msg.attach_alternative(
            render_to_string("attendance/mail/external_attendees.html", context),
            "text/html",
        )
        msg.content_subtype = "html"
        msg.send()


class EntryCleanupTask(PeriodicTask):
    run_every = timedelta(minutes=15)

    def run(self, **kwargs):
        from outpost.django.campusonline.models import Student
        from .models import Entry

        for e in Entry.objects.all():
            try:
                Student.objects.get(pk=e.student_id)
            except Student.DoesNotExist:
                logger.warn(f"Removing student {e.student_id} link for entry {e.pk}")
                if not e.status:
                    e.status = dict()
                e.status["student"] = e.student_id
                e.student = None
                e.save()


class CampusOnlineEntryCleanupTask(PeriodicTask):
    """
    End all CO entries that were registered for a room but where not assigned
    to a holding in a certain timeframe.

    It works by covering cases where a holding was never started:

    A student registers ahead of the offical start time of a holding:

        Search for a planned holding happening after the registration time.
        Then check if this holding has already ended according to CAMPUSonline.
        If so, the CO entry is canceled.

    A student registers during the official holding time:

        If there is at least a configurable buffer of time between the
        registration time and the next planned holding, cancel it.

        If the CO entry was registered within the buffer of time to a
        subsequent holding, leave the CO entry as it is.
    """

    run_every = timedelta(minutes=5)

    def run(self, **kwargs):
        from .models import CampusOnlineEntry

        now = timezone.now()
        logger.info(f"Cleaning up CO entries")
        for e in CampusOnlineEntry.objects.filter(state="created"):
            cgt_base = CourseGroupTerm.objects.filter(
                room=e.room, start__date=e.created, end__date=e.created
            ).order_by("start")
            # Check for next or current CGT
            cgt = cgt_base.filter(
                start__lte=e.created + settings.ATTENDANCE_CAMPUSONLINE_ENTRY_LIFETIME,
                end__gte=e.created,
            ).first()
            if not cgt:
                # The is no planned holding left for today.
                if e.created + settings.ATTENDANCE_CAMPUSONLINE_ENTRY_LIFETIME > now:
                    # CO entry still inside entry lifetime, do nothing.
                    continue
            else:
                if e.created > cgt.start:
                    # CO entry is within planned holding, look for start of
                    # next planned holding.
                    cgt_next = cgt_base.filter(start__gte=cgt.end).first()
                    if (
                        cgt_next.start - settings.ATTENDANCE_CAMPUSONLINE_ENTRY_BUFFER
                        < e.created
                    ):
                        # CO entry was created within buffer ahead of the
                        # following holding, do nothing.
                        continue
                if cgt.end > now:
                    # Holding is still within planned time range, do nothing.
                    continue
            logger.debug(f"Canceling CO entry {e}")
            e.cancel()
            e.save()


class CampusOnlineHoldingCleanupTask(PeriodicTask):
    """
    Clean up holdings that were not ended manually.

    Ends when current time is greater than start of holding plus official time from
    CAMPUSonline holding plus overdraft time from settings.
    """

    run_every = timedelta(minutes=5)

    def run(self, **kwargs):
        from .models import CampusOnlineHolding

        now = timezone.now()
        for h in CampusOnlineHolding.objects.filter(state="running"):
            period = h.course_group_term.end - h.course_group_term.start
            if h.initiated + period + settings.ATTENDANCE_HOLDING_OVERDRAFT < now:
                h.end(finished=h.initiated + period)
                h.save()
