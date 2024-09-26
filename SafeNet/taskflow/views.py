import os
import pandas as pd
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.views import View
from .models import Project, Task, Log
from .forms import ProjectForm, TaskForm
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.contrib import messages
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from .forms import FileUploadForm
from .models import File
from .models import CSVFile
from .forms import CSVFileForm


# Home view
def home(request):
    return render(request, 'taskflow/home.html')

# Custom decorator to redirect to login if not authenticated
def custom_login_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        else:
            return redirect('login')  # Redirect to login if not authenticated

    return _wrapped_view

# Dashboard view
@custom_login_required
def dashboard(request):
    projects = Project.objects.filter(owner=request.user)
    tasks = Task.objects.filter(assigned_to=request.user)
    alerts = tasks.filter(due_date__gte=date.today(), due_date__lt=date.today() + timedelta(days=3))
    logs = Log.objects.filter(user=request.user).order_by('-timestamp')[:10]  # Get last 10 logs

    # Fetch recent file deletion alerts for superusers
    recent_alerts = Log.objects.filter(action__icontains='deleted', timestamp__gte=date.today()).order_by('-timestamp')[:5]

    context = {
        'projects': projects,
        'tasks': tasks,
        'alerts': alerts,
        'logs': logs,
        'recent_alerts': recent_alerts,  # Include recent alerts in context
    }
    return render(request, 'taskflow/dashboard.html', context)


# Project-related views
@custom_login_required
def project_list(request):
    projects = Project.objects.filter(assigned_users=request.user)
    return render(request, 'taskflow/project_list.html', {'projects': projects})

@custom_login_required
def add_users_to_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    users = User.objects.exclude(id__in=project.assigned_users.all())

    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')
        if user_ids:
            project.assigned_users.add(*user_ids)
            log_action(request.user, f"Added users to project: {project.name}")
            messages.success(request, 'Users added successfully.')
        else:
            messages.warning(request, 'No users selected.')
        return redirect('project_detail', project_id=project.id)

    return render(request, 'taskflow/add_users.html', {'project': project, 'users': users})

@custom_login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user  # Set the owner to the current user
            project.save()
            project.assigned_users.add(request.user)  # Automatically assign the creator
            log_action(request.user, f"Created project: {project.name}")
            messages.success(request, f'Project "{project.name}" created successfully.')
            return redirect('dashboard')  # Change this if needed
    else:
        form = ProjectForm()
    return render(request, 'taskflow/project_form.html', {'form': form})

@custom_login_required
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            log_action(request.user, f"Edited project: {project.name}")
            messages.success(request, 'Project updated successfully.')
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'taskflow/edit_project.html', {'form': form, 'project': project})

@custom_login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner=request.user)
    if request.method == 'POST':
        project.delete()
        log_action(request.user, f"Deleted project: {project.name}")
        messages.success(request, f'Project "{project.name}" deleted successfully.')
        return redirect('dashboard')
    return render(request, 'taskflow/project_confirm_delete.html', {'project': project})

@custom_login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, assigned_users=request.user)
    tasks = project.tasks.all()  # Access tasks using the related name

    return render(request, 'taskflow/project_detail.html', {'project': project, 'tasks': tasks})


# Task-related views
@custom_login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    return render(request, 'taskflow/task_detail.html', {'task': task})

# create task view
def create_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.save()
            assigned_users = request.POST.getlist('assigned_to')  # Get all checked user IDs
            for user_id in assigned_users:
                task.assigned_to.add(User.objects.get(id=user_id))
            return redirect('task_list')  # Redirect after successful creation
    else:
        form = TaskForm()

    projects = Project.objects.all()
    users = User.objects.all()

    return render(request, 'taskflow/create_task.html', {
        'form': form,
        'projects': projects,
        'users': users,
    })

# edit task view
@custom_login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        # Debugging: Print out the POST data
        print("POST data:", request.POST)

        assigned_users = request.POST.getlist('assigned_to')
        task.title = request.POST['title']
        task.description = request.POST['description']
        task.start_date = request.POST['start_date']
        task.due_date = request.POST['due_date']

        # Debugging: Check assigned users list
        print("Assigned Users:", assigned_users)

        # Clear previous assigned users and add new ones
        task.assigned_to.clear()
        for user_id in assigned_users:
            task.assigned_to.add(User.objects.get(id=user_id))

        # Get the project ID from the POST data
        project_id = request.POST.get('project')
        print("Selected Project ID:", project_id)  # Debugging project ID

        if project_id:  # If project is selected, assign it to the task
            task.project_id = project_id
        else:
            task.project_id = None  # If no project is selected, set it to None

        task.save()  # Save the task after modifications
        return redirect('task_list')  # Redirect after successful update

    # Get list of IDs for assigned users
    assigned_user_ids = task.assigned_to.values_list('id', flat=True)

    return render(request, 'taskflow/edit_task.html', {
        'task': task,
        'projects': Project.objects.all(),
        'users': User.objects.all(),
        'assigned_user_ids': assigned_user_ids,
    })

@custom_login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    if request.method == 'POST':
        task.delete()
        log_action(request.user, f"Deleted task: {task.title}")
        messages.success(request, f'Task "{task.title}" deleted successfully.')
        return redirect('task_list')  # Redirect to task list after deletion
    return render(request, 'taskflow/task_confirm_delete.html', {'task': task})

@custom_login_required
def task_list(request):
    tasks = Task.objects.filter(assigned_to=request.user)  # Fetch user's tasks
    return render(request, 'taskflow/task_list.html', {
        'tasks': tasks,
    })


# Login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'taskflow/login.html')


# Logout view
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


# User registration view
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created for {user.username}.')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'taskflow/register.html', {'form': form})


# Signup view
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully. Please log in.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'taskflow/signup.html', {'form': form})


# Helper function to log actions
def log_action(user, action):
    Log.objects.create(user=user, action=action)


# Notify users about new tasks via Channels
def notify_users(users, task):
    channel_layer = get_channel_layer()
    for user in users:
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                'type': 'send_notification',
                'message': json.dumps({
                    'task_title': task.title,
                    'project_name': task.project.name,
                    'task_id': task.id
                }),
            }
        )


# File upload view
@custom_login_required
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save(commit=False)
            uploaded_file.uploaded_by = request.user  # Ensure the uploader is the current user
            uploaded_file.save()
            log_action(request.user, f"Uploaded file: {uploaded_file.name}")
            messages.success(request, f'File "{uploaded_file.name}" uploaded successfully.')
            return redirect('file_list')
    else:
        form = FileUploadForm()
    return render(request, 'taskflow/upload_file.html', {'form': form})


def upload_csv(request):
    if request.method == 'POST':
        form = CSVFileForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('csv_file_list')
        else:
            return HttpResponse("Invalid file. Only CSV files are allowed.")
    else:
        form = CSVFileForm()

    return render(request, 'taskflow/upload_csv.html', {'form': form})


def csv_file_list(request):
    csv_files = CSVFile.objects.all()
    return render(request, 'taskflow/csv_file_list.html', {'csv_files': csv_files})

# File list view
@custom_login_required
def file_list(request):
    files = File.objects.filter(uploaded_by=request.user)  # Only show user's files
    return render(request, 'taskflow/file_list.html', {'files': files})

# View file content
@custom_login_required
def view_file(request, file_id):
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user)  # Ensure user owns the file
    file_path = os.path.join(settings.MEDIA_ROOT, file.file.name)

    data = pd.read_csv(file_path).to_dict(orient='records')
    return render(request, 'taskflow/view_file.html', {'file': file, 'data': data})

# Delete file view
@custom_login_required
def delete_file(request, file_id):
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user)  # Ensure user owns the file
    if request.method == 'POST':
        file_name = file.name
        file.delete()
        log_action(request.user, f"Deleted file: {file_name}")
        messages.success(request, f'File "{file_name}" deleted successfully.')
        return redirect('file_list')
    return render(request, 'taskflow/file_confirm_delete.html', {'file': file})

# Modify file content
@custom_login_required
def modify_file(request, file_id):
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user)
    file_path = os.path.join(settings.MEDIA_ROOT, file.file.name)

    try:
        # Read the CSV file into a DataFrame
        data = pd.read_csv(file_path)
    except Exception as e:
        messages.error(request, "Error reading file for viewing.")
        return redirect('file_list')

    # Convert DataFrame to dictionary for rendering
    data_list = data.to_dict(orient='records')
    return render(request, 'taskflow/view_file.html', {'file': file, 'data': data_list})


@custom_login_required
def data_view(request):
    uploaded_data = None  # Variable to store the data to be displayed
    uploaded_files = CSVFile.objects.all()  # Get all uploaded files, no user filtering

    # Handle file upload
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Assign the current user to the uploaded_by field
            uploaded_file = form.save(commit=False)
            uploaded_file.uploaded_by = request.user  # Assign the current user
            uploaded_file.save()
            messages.success(request, f'File "{uploaded_file.file.name}" uploaded successfully.')

            # Log the file upload action
            log_action(request.user, f'Uploaded file: {uploaded_file.file.name}')

            # Load the CSV data into a DataFrame
            file_path = uploaded_file.file.path
            uploaded_data = pd.read_csv(file_path).to_dict(orient='records')  # Convert to a list of dictionaries

    else:
        form = FileUploadForm()

    # Handle file selection from dropdown or file deletion
    if request.method == 'GET':
        file_id = request.GET.get('selected_file')

        if file_id:
            if 'delete' in request.GET:
                # Delete the selected file
                file_to_delete = get_object_or_404(CSVFile, id=file_id)
                file_to_delete.delete()
                messages.success(request, 'File deleted successfully.')

                # Log the file deletion action
                log_action(request.user, f'Deleted file: {file_to_delete.file.name}')

                return redirect('data_view')  # Redirect to refresh the file list
            else:
                # Load the selected file data
                uploaded_file = get_object_or_404(CSVFile, id=file_id)
                file_path = uploaded_file.file.path
                uploaded_data = pd.read_csv(file_path).to_dict(orient='records')  # Convert to a list of dictionaries

                # Log the file selection action
                log_action(request.user, f'Selected file: {uploaded_file.file.name} for viewing')

    return render(request, 'taskflow/data_view.html', {
        'form': form,
        'uploaded_files': uploaded_files,  # Pass all uploaded files for dropdown
        'data': uploaded_data  # Pass the uploaded data to the template
    })


class FileUploadView(View):
    def get(self, request):
        form = FileUploadForm()
        return render(request, 'taskflow/upload_csv.html', {'form': form})

    def post(self, request):
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save(commit=False)
            uploaded_file.uploaded_by = request.user
            uploaded_file.save()
            messages.success(request, f'File "{uploaded_file.file.name}" uploaded successfully.')
            return redirect('data_view')  # Redirect to your desired view

        return render(request, 'taskflow/upload_csv.html', {'form': form})


def search_files(request):
    query = request.GET.get('query', '')
    if query:
        files = File.objects.filter(file__icontains=query, uploaded_by=request.user)  # Adjust the field
    else:
        files = File.objects.filter(uploaded_by=request.user)

    return render(request, 'taskflow/file_list.html', {'files': files})

from .models import CSVFile

def download_file(request):
    if request.method == "POST":
        file_id = request.POST.get('file_id')
        try:
            uploaded_file = CSVFile.objects.get(id=file_id)
            response = HttpResponse(uploaded_file.file, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{uploaded_file.file.name}"'
            return response
        except CSVFile.DoesNotExist:
            return HttpResponse(status=404)
    else:
        return HttpResponse(status=400)