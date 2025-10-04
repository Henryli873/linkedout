from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.search, name='search'),
    path("suggested/", views.suggest_jobs, name="suggested_jobs"),
    path('post/', views.post_job, name='post_job'),
    path('my-postings/', views.my_postings, name='my_postings'),
    path('<int:pk>/', views.job_detail, name='job_detail'),
    path('<int:pk>/edit/', views.edit_post, name='edit_post'),
    path('<int:pk>/apply/', views.apply, name='apply'),
    path('apply/thanks/', views.apply_thanks, name='apply_thanks'),
    # Candidate application views
    path("applications/", views.my_applications, name="my_applications"),
    path("applications/<int:pk>/", views.application_details, name="application_details"),

    # Recruiter application management
    path("recruiter/applications/", views.recruiter_applications, name="recruiter_applications"),
    path("recruiter/applications/<int:pk>/update/", views.update_application_status, name="update_status"),
    path("recruiter/applications/update-status/", views.recruiter_update_application_status_ajax, name="recruiter_update_status_ajax"),
    path('map/', views.interactive_map, name='interactive_map'),
    path('map/nearby/', views.jobs_nearby, name='jobs_nearby'),
]
