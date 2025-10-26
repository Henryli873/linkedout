from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('edit/', views.edit_profile, name='edit_profile'),
    path('signup/', views.signup, name='signup'),
    path('applicants/', views.find_applicants, name='find_applicants'),
    path('message/<int:pk>/', views.message_user_view, name='message_user'),
    path('email/<int:pk>/', views.email_user_view, name='email_user'),
    path('messages/', views.messages_inbox, name='messages_inbox'),
    path('messages/<int:pk>/', views.message_detail, name='message_detail'),
    path('saved/', views.saved_profiles, name='saved_profiles'),
    path('save/<int:pk>/', views.save_profile_view, name='save_profile'),
    path('<str:username>/', views.profile_detail, name='profile_detail'),
]

