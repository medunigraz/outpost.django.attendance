from django.utils.translation import gettext_lazy as _
from django_filters import (
    CharFilter,
    ModelChoiceFilter,
)
from django_filters.rest_framework import (
    filters,
    filterset,
)

from outpost.django.campusonline.models import (
    CourseGroupTerm,
    Room,
)

from . import models


class CampusOnlineHoldingFilter(filterset.FilterSet):
    '''
    ## Filters

    To filter for exact value matches:

        ?<fieldname>=<value>

    For advanced filtering use lookups:

        ?<fieldname>__<lookup>=<value>

    Possible lookups:

      - `initiated`: `exact`, `gt`, `gte`, `lt`, `lte`, `date`
      - `finished`: `exact`, `gt`, `gte`, `lt`, `lte`, `date`
    '''
    #course_group_term = ModelChoiceFilter(
    #    queryset=CourseGroupTerm.objects.select_related(
    #        'coursegroup',
    #        'coursegroup__course',
    #        'person',
    #        'room',
    #    )
    #)

    class Meta:
        model = models.CampusOnlineHolding
        fields = {
            'state': (
                'exact',
            ),
            'course_group_term': (
                'exact',
            ),
            'room': (
                'exact',
            ),
            'initiated': (
                'exact',
                'gt',
                'lt',
                'gte',
                'lte',
                'date',
            ),
            'finished': (
                'exact',
                'gt',
                'lt',
                'gte',
                'lte',
                'date',
            ),
        }


class CampusOnlineEntryFilter(filterset.FilterSet):
    '''
    ## Filters

    To filter for exact value matches:

        ?<fieldname>=<value>

    For advanced filtering use lookups:

        ?<fieldname>__<lookup>=<value>

    Possible lookups:

      - `initiated`: `exact`, `gt`, `gte`, `lt`, `lte`, `date`
      - `finished`: `exact`, `gt`, `gte`, `lt`, `lte`, `date`
    '''

    class Meta:
        model = models.CampusOnlineEntry
        fields = {}
