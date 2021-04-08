from datetime import timedelta

from appconf import AppConf
from django.conf import settings


class AttendanceAppConf(AppConf):
    CAMPUSONLINE_HOLDING_OVERDRAFT = timedelta(minutes=15)
    CAMPUSONLINE_ENTRY_LIFETIME = timedelta(minutes=45)
    CAMPUSONLINE_ENTRY_BUFFER_END = timedelta(minutes=15)
    CAMPUSONLINE_CONTINUATION_BUFFER = timedelta(minutes=30)
    PHONE_NUMBER_REGION = "AT"
    STUDENT_MATRICULATION_MASK = '*'
    STUDENT_MATRICULATION_UNMASKED = 3

    class Meta:
        prefix = "attendance"
