# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-02 12:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("attendance", "0004_auto_20170929_0858")]

    operations = [
        migrations.AlterField(
            model_name="terminal",
            name="enabled",
            field=models.BooleanField(default=True),
        )
    ]
