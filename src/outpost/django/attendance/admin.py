from django.contrib import admin
from django.utils.html import mark_safe

from . import models


@admin.register(models.Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("student", "terminal", "created")
    list_filter = ("terminal",)
    search_fields = ("student__first_name", "student__last_name", "terminal__hostname")
    date_hierarchy = "created"


@admin.register(models.Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ("pk", "hostname", "enabled", "online", "list_rooms")
    list_filter = ("enabled", "online")
    search_fields = ("hostname", "rooms")
    readonly_fields = ("online",)

    def list_rooms(self, obj):
        rooms = "".join([f"<li>{r.name_full}</li>" for r in obj.rooms.all()])
        return mark_safe(f"<ul>{rooms}</ul>")


class CampusOnlineEntryInline(admin.TabularInline):
    model = models.CampusOnlineEntry


@admin.register(models.CampusOnlineHolding)
class CampusOnlineHoldingAdmin(admin.ModelAdmin):
    inlines = [CampusOnlineEntryInline]


class StatisticsEntryInline(admin.TabularInline):
    model = models.StatisticsEntry
    readonly_fields = ("incoming", "outgoing", "state")
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(models.Statistics)
class StatisticsAdmin(admin.ModelAdmin):
    inlines = [StatisticsEntryInline]
