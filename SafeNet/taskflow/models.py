from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from django.core.exceptions import ValidationError
import os

class Project(models.Model):
    name = models.CharField(max_length=255, default='Untitled Project')
    description = models.TextField(default='No description provided.')
    start_date = models.DateField(default=date.today)
    end_date = models.DateField(default=date.today() + timedelta(days=30))
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    assigned_users = models.ManyToManyField(User, related_name='projects', blank=True)

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("End date must be after start date.")

    def __str__(self):
        return self.name

class Task(models.Model):
    title = models.CharField(max_length=255, default="Untitled Task")
    description = models.TextField(blank=True, default='No description provided')
    start_date = models.DateField()
    due_date = models.DateField()
    assigned_to = models.ManyToManyField(User, related_name='tasks_assigned', blank=True)  # Changed to ManyToManyField
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.SET_NULL, null=True, blank=True)  # Allow null and blank values

    def __str__(self):
        return self.title


class File(models.Model):
    file = models.FileField(upload_to='uploads/', null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, default=1)  # Adjust default user ID

class Log(models.Model):
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"

def validate_csv(file):
    ext = os.path.splitext(file.name)[1]
    if ext.lower() != '.csv':
        raise ValidationError("Only .csv files are allowed.")

class CSVFile(models.Model):
    file = models.FileField(upload_to='csv_files/', validators=[validate_csv])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
