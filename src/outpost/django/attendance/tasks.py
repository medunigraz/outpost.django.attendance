import logging
from datetime import timedelta

from celery.task import PeriodicTask, Task
from celery.task.schedules import crontab
from django.db.models import Q
from django.utils import timezone


logger = logging.getLogger(__name__)


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
    run_every = timedelta(minutes=5)

    def run(self, **kwargs):
        from .models import CampusOnlineEntry

        past = timezone.now() - timedelta(hours=12)
        logger.info(f"Cleaning up CO entries older than {past}")
        cond = {"state": "created", "incoming__created__lt": past}
        for e in CampusOnlineEntry.objects.filter(**cond):
            logger.debug(f"Canceling CO entry {e}")
            e.cancel()
            e.save()


class CampusOnlineHoldingCleanupTask(PeriodicTask):
    run_every = timedelta(minutes=5)

    def run(self, **kwargs):
        from .models import CampusOnlineHolding

        now = timezone.now()
        # TODO: Fix filter to find holding that have recently ended
        for h in CampusOnlineHolding.objects.filter(state="running"):
            period = h.course_group_term.end - h.course_group_term.start
            if h.initiated + period + timedelta(hours=2) < now:
                h.end(finished=h.initiated + period)
                h.save()
