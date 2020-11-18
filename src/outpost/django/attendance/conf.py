from datetime import timedelta

from appconf import AppConf
from django.conf import settings


class AttendanceAppConf(AppConf):
    CONTINUATION_BUFFER = timedelta(minutes=30)
    HOLDING_OVERDRAFT = timedelta(minutes=15)
    CAMPUSONLINE_ENTRY_LIFETIME = timedelta(minutes=45)
    CAMPUSONLINE_ENTRY_BUFFER_END = timedelta(minutes=15)
    PHONE_NUMBER_REGION = "AT"

    class Meta:
        prefix = "attendance"
