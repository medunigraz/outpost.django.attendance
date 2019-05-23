from rest_flex_fields import FlexFieldsModelSerializer
from rest_framework import exceptions, serializers

from outpost.django.campusonline.models import Person
from outpost.django.campusonline.serializers import StudentSerializer

from . import models


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

    expandable_fields = {
        "course_group_term": (
            f"outpost.django.campusonline.serializers.CampusOnlineEntrySerializer",
            {"source": "course_group_term", "read_only": True},
        ),
        "entries": (
            f"{__package__}.CampusOnlineEntrySerializer",
            {"source": "holding", "read_only": True, "many": True},
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
        )
        read_only_fields = ("id", "state", "initiated", "finished", "entries")

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
            {"source": "incoming.student", "read_only": False},
        ),
    }

    class Meta:
        model = models.CampusOnlineEntry
        fields = ("id", "assigned", "ended", "state", "holding", "student")


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
