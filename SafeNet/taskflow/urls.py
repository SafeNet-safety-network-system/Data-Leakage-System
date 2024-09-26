from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Home page
    path('dashboard/', views.dashboard, name='dashboard'),  # Dashboard page

    # Project-related paths
    path('projects/', views.project_list, name='project_list'),  # List of all projects
    path('projects/create/', views.create_project, name='create_project'),  # Create a new project
    path('projects/edit/<int:project_id>/', views.edit_project, name='edit_project'),  # Edit a project
    path('projects/delete/<int:project_id>/', views.delete_project, name='delete_project'),  # Delete a project
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),  # Project details
    path('projects/<int:project_id>/add_users/', views.add_users_to_project, name='add_users_to_project'),

    # Task-related paths
    path('tasks/create/', views.create_task, name='create_task'),  # Create a new task
    path('tasks/edit/<int:task_id>/', views.edit_task, name='edit_task'),  # Edit a task
    path('tasks/', views.task_list, name='task_list'),  # List of all tasks
    path('tasks/delete/<int:task_id>/', views.delete_task, name='delete_task'),  # Delete a task
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),  # Task details

    # Authentication paths
    path('login/', views.login_view, name='login'),  # User login
    path('logout/', views.logout_view, name='logout'),  # User logout
    path('register/', views.register, name='register'),  # User registration
    path('signup/', views.signup, name='signup'),  # User signup

    # Data view path
    path('data-view/', views.data_view, name='data_view'),
    path('upload/', views.upload_csv, name='upload_csv'),
    path('files/', views.csv_file_list, name='csv_file_list'), # List all files uploaded by the user
    path('files/view/<int:file_id>/', views.view_file, name='view_file'),  # View file content
    path('files/delete/<int:file_id>/', views.delete_file, name='delete_file'),  # Delete a file
    path('files/edit/<int:file_id>/', views.modify_file, name='modify_file'),  # Edit file content
    path('download_file/', views.download_file, name='download_file'),
    path('search-files/', views.search_files, name='search_files'), # File upload view
]
