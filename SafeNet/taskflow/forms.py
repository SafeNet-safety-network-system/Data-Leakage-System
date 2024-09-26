from django import forms
from django.contrib.auth.models import User
from .models import Task, Project, CSVFile

class ProjectForm(forms.ModelForm):
    assigned_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'start_date', 'end_date', 'assigned_users']


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'start_date', 'due_date', 'assigned_to', 'project']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        self.fields['assigned_to'].widget = forms.CheckboxSelectMultiple()

        # Populate project choices with an optional "No Project" option
        self.fields['project'].queryset = Project.objects.all()
        self.fields['project'].required = False  # Allow for no project selection

    def clean_project(self):
        project = self.cleaned_data.get('project')
        return project if project else None  # Return None if no project is selected

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = CSVFile
        fields = ['file']


class CSVFileForm(forms.Form):
    csv_file = forms.FileField(label='Upload CSV File')
