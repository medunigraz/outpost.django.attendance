from django.contrib import admin

from . import models


@admin.register(models.Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'terminal',
        'created',

    )
    list_filter = (
        'terminal',
    )
    search_fields = (
        'student__first_name',
        'student__last_name',
        'terminal__hostname',
    )
    date_hierarchy = 'created'


@admin.register(models.Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = (
        'hostname',
        'enabled',
        'online',
    )
    list_filter = (
        'enabled',
        'online',
    )
    search_fields = (
        'hostname',
    )


class CampusOnlineEntryInline(admin.TabularInline):
    model = models.CampusOnlineEntry


@admin.register(models.CampusOnlineHolding)
class CampusOnlineHoldingAdmin(admin.ModelAdmin):
    inlines = [
        CampusOnlineEntryInline,
    ]


class StatisticsEntryInline(admin.TabularInline):
    model = models.StatisticsEntry
    readonly_fields = (
        'incoming',
        'outgoing',
        'state',
    )
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(models.Statistics)
class StatisticsAdmin(admin.ModelAdmin):
    inlines = [
        StatisticsEntryInline,
    ]
