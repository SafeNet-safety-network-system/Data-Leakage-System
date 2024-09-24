from django.contrib import admin
from .models import Project, Task, CSVFile

admin.site.register(Project)
admin.site.register(Task)
@admin.register(CSVFile)
class CSVFileAdmin(admin.ModelAdmin):
    list_display = ('file', 'uploaded_at')