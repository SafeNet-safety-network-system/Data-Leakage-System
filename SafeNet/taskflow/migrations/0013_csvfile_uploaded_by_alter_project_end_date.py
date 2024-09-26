# Generated by Django 5.0 on 2024-09-26 03:43

import datetime
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taskflow', '0012_alter_task_project'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='csvfile',
            name='uploaded_by',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='project',
            name='end_date',
            field=models.DateField(default=datetime.date(2024, 10, 26)),
        ),
    ]
