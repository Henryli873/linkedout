from django.contrib import admin
from .models import Profile
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from import_export.admin import ImportExportModelAdmin

User = get_user_model()


@admin.register(Profile)
class ProfileAdmin(ImportExportModelAdmin):
	list_display = ('user', 'headline')
	search_fields = ('user__username', 'headline', 'skills')


try:
	admin.site.register(User, UserAdmin)
except admin.sites.AlreadyRegistered:
	# User is already registered by another app/config
	pass
