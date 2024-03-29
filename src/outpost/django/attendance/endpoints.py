from . import api

v1 = [
    (r"attendance/terminal", api.TerminalViewSet, "attendance-terminal"),
    (
        r"attendance/campusonlineholding",
        api.CampusOnlineHoldingViewSet,
        "attendance-campusonline-holding",
    ),
    (
        r"attendance/campusonlineentry",
        api.CampusOnlineEntryViewSet,
        "attendance-campusonline-entry",
    ),
    (
        r"attendance/manualcampusonlineentry",
        api.ManualCampusOnlineEntryViewSet,
        "attendance-manualcampusonline-entry",
    ),
    (r"attendance/roomstate", api.RoomStateViewSet, "attendance-roomstate"),
    (r"attendance/statistics", api.StatisticsViewSet, "attendance-statistics"),
]
