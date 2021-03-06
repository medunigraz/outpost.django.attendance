# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-03-06 15:41
from __future__ import unicode_literals

from django.db import migrations


def assign_room(apps, schema_editor):
    Entry = apps.get_model("attendance", "Entry")
    for entry in Entry.objects.all():
        entry.room_id = entry.terminal.room_id
        entry.save()


class Migration(migrations.Migration):

    dependencies = [("attendance", "0013_auto_20190306_1639")]

    operations = [migrations.RunPython(assign_room, migrations.RunPython.noop)]
