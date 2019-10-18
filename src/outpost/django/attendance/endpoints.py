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
    (r"attendance/statistics", api.StatisticsViewSet, "attendance-statistics"),
]
