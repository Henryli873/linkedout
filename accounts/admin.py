from django.contrib import admin
from .models import Profile
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'headline')
	search_fields = ('user__username', 'headline', 'skills')


try:
	admin.site.register(User, UserAdmin)
except admin.sites.AlreadyRegistered:
	# User is already registered by another app/config
	pass
