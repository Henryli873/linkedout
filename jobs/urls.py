from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.search, name='search'),
    path('<int:pk>/', views.job_detail, name='job_detail'),
    path('<int:pk>/apply/', views.apply, name='apply'),
    path('apply/thanks/', views.apply_thanks, name='apply_thanks'),
]
