from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from outpost.django.campusonline.models import Person, Room, Student
from outpost.django.campusonline.serializers import AuthenticatedStudentSerializer
from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import exceptions, serializers
from rest_framework.exceptions import ValidationError

from .conf import settings
from . import models


class MaskedStudentSerializer(AuthenticatedStudentSerializer):
    matriculation = serializers.SerializerMethodField()

    class Meta(AuthenticatedStudentSerializer.Meta):
        fields = AuthenticatedStudentSerializer.Meta.fields + ("matriculation",)

    def get_matriculation(self, obj):
        char = settings.ATTENDANCE_STUDENT_MATRICULATION_MASK
        mask = settings.ATTENDANCE_STUDENT_MATRICULATION_UNMASKED
        return char * (len(obj.matriculation) - mask) + obj.matriculation[-mask:]


class TerminalSerializer(FlexFieldsModelSerializer):

    expandable_fields = {
        "rooms": (
            "outpost.django.campusonline.serializers.RoomSerializer",
            {"source": "rooms", "many": True},
        )
    }

    class Meta:
        model = models.Terminal
        fields = ("id", "rooms", "config")


class EntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Entry
        fields = ("terminal", "created")


class CampusOnlineHoldingSerializer(FlexFieldsModelSerializer):
    """
    ## Expansions

    To activate relation expansion add the desired fields as a comma separated
    list to the `expand` query parameter like this:

        ?expand=<field>,<field>,<field>,...

    The following relational fields can be expanded:

     * `course_group_term`
     * `entries`

    """
    accredited = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    expandable_fields = {
        "course_group_term": (
            "outpost.django.campusonline.serializers.CourseGroupTermSerializer",
            {"source": "course_group_term", "read_only": True},
        ),
        "entries": (
            f"{__package__}.CampusOnlineEntrySerializer",
            {"source": "entries", "read_only": True, "many": True},
        ),
        "manual_entries": (
            f"{__package__}.ManualCampusOnlineEntrySerializer",
            {"source": "manual_entries", "read_only": True, "many": True},
        ),
        "accredited": (
            f"{__package__}.MaskedStudentSerializer",
            {"source": "accredited", "read_only": True, "many": True},
        ),
    }

    class Meta:
        model = models.CampusOnlineHolding
        fields = (
            "id",
            "state",
            "initiated",
            "finished",
            "course_group_term",
            "room",
            "entries",
            "manual_entries",
            "accredited",
        )
        read_only_fields = ("id", "state", "initiated", "finished", "entries", "accredited")

    def save(self):
        request = self.context.get("request", None)
        if not request:
            raise serializers.ValidationError("No request found in context.")
        if not request.user.is_authenticated:
            raise exceptions.NotAuthenticated(
                "Must be authenticated to create holding."
            )
        try:
            lecturer = Person.objects.get(username=request.user.username)
        except Person.DoesNotExist:
            raise exceptions.PermissionDenied(
                "Only users with CAMPUSonline accounts can create holdings"
            )
        self.validated_data["lecturer"] = lecturer
        return super().save()


class CampusOnlineEntrySerializer(FlexFieldsModelSerializer):
    """
    ## Expansions

    To activate relation expansion add the desired fields as a comma separated
    list to the `expand` query parameter like this:

        ?expand=<field>,<field>,<field>,...

    The following relational fields can be expanded:

     * `holding`
     * `student`

    """

    student = serializers.PrimaryKeyRelatedField(
        source="incoming.student", read_only=True
    )

    expandable_fields = {
        "holding": (
            f"{__package__}.CampusOnlineHoldingSerializer",
            {"source": "holding", "read_only": True},
        ),
        "student": (
            "outpost.django.campusonline.serializers.StudentSerializer",
            {"source": "incoming.student", "read_only": True},
        ),
    }

    class Meta:
        model = models.CampusOnlineEntry
        fields = (
            "id",
            "assigned",
            "ended",
            "state",
            "holding",
            "student",
            "accredited",
        )
        read_only_fields = ("id", "assigned", "ended", "state", "accredited")


class ManualCampusOnlineEntrySerializer(FlexFieldsModelSerializer):
    """
    ## Expansions

    To activate relation expansion add the desired fields as a comma separated
    list to the `expand` query parameter like this:

        ?expand=<field>,<field>,<field>,...

    The following relational fields can be expanded:

     * `holding`
     * `student`

    """

    expandable_fields = {
        "holding": (
            f"{__package__}.CampusOnlineHoldingSerializer",
            {"source": "holding", "read_only": True},
        ),
        "student": (
            "outpost.django.campusonline.serializers.StudentSerializer",
            {"source": "student", "read_only": True},
        ),
        "room": (
            "outpost.django.campusonline.serializers.RoomSerializer",
            {"source": "room", "read_only": True},
        ),
    }

    class Meta:
        model = models.ManualCampusOnlineEntry
        fields = (
            "id",
            "assigned",
            "room",
            "ended",
            "state",
            "holding",
            "student",
            "accredited",
        )
        read_only_fields = ("id", "assigned", "ended", "state", "accredited")


class RoomStateSerializer(FlexFieldsModelSerializer):
    """
    ## Expansions

    To activate relation expansion add the desired fields as a comma separated
    list to the `expand` query parameter like this:

        ?expand=<field>,<field>,<field>,...

    The following relational fields can be expanded:

     * `students`

    """
    students = serializers.SerializerMethodField()
    #students = AuthenticatedStudentSerializer(source="get_students", many=True)

    expandable_fields = {
        "students": (
            "outpost.django.campusonline.serializers.StudentSerializer",
            {"source": "students", "read_only": True, "many": True},
        ),
    }

    class Meta:
        model = Room
        fields = (
            "id",
            "students",
        )
        read_only_fields = ("id", "students")

    def get_students(self, obj):
        s = Student.objects.filter(
            Q(attendance__campusonlineentry__room=obj) | Q(manualcampusonlineentry__room=obj),
            roomallocation__room=obj,
            roomallocation__onsite=False,
            roomallocation__start__lt=timezone.now(),
            roomallocation__end__gt=timezone.now(),
        )
        # TODO: Check vaccination status
        return AuthenticatedStudentSerializer(s, many=True).data


class StatisticsEntrySerializer(serializers.ModelSerializer):
    incoming = EntrySerializer(read_only=True)
    outgoing = EntrySerializer(read_only=True)

    class Meta:
        model = models.StatisticsEntry
        fields = ("incoming", "outgoing")


class StatisticsSerializer(serializers.ModelSerializer):
    entries = StatisticsEntrySerializer(many=True, read_only=True)

    class Meta:
        model = models.Statistics
        fields = ("name", "entries")
