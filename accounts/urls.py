from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
	path('edit/', views.edit_profile, name='edit_profile'),
	path('signup/', views.signup, name='signup'),
	path('<str:username>/', views.profile_detail, name='profile_detail'),
]
