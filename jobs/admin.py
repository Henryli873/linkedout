from django.contrib import admin
from .models import Job, Application


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
	list_display = ('title', 'company', 'location', 'posted_at')
	search_fields = ('title', 'company', 'location')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
	list_display = ('job', 'user', 'submitted_at')
	search_fields = ('job__title', 'user__username')
