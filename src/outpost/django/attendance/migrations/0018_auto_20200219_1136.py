# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-02-19 10:36
from __future__ import unicode_literals

from django.db import migrations, models
import outpost.django.base.fields


class Migration(migrations.Migration):

    dependencies = [("attendance", "0017_auto_20191018_1010")]

    operations = [
        migrations.AlterField(
            model_name="terminal",
            name="behaviour",
            field=outpost.django.base.fields.ChoiceArrayField(
                base_field=models.CharField(
                    choices=[
                        (
                            "outpost.django.attendance.plugins.DebugTerminalBehaviour",
                            "Debugger",
                        ),
                        (
                            "outpost.django.attendance.plugins.CampusOnlineTerminalBehaviour",
                            "CAMPUSonline",
                        ),
                        (
                            "outpost.django.attendance.plugins.StatisticsTerminalBehaviour",
                            "Statistiken",
                        ),
                    ],
                    max_length=256,
                ),
                default=list,
                size=None,
            ),
        )
    ]