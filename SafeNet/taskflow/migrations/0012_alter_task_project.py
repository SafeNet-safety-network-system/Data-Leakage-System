# Generated by Django 5.0 on 2024-09-23 10:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taskflow', '0011_alter_project_end_date_remove_task_assigned_to_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tasks', to='taskflow.project'),
        ),
    ]
