from django.contrib import admin
from .models import Job, Application
from import_export.admin import ImportExportModelAdmin


@admin.register(Job)
class JobAdmin(ImportExportModelAdmin):
	list_display = ('title', 'company', 'location', 'posted_at')
	search_fields = ('title', 'company', 'location')


@admin.register(Application)
class ApplicationAdmin(ImportExportModelAdmin):
	list_display = ('job', 'user', 'submitted_at')
	search_fields = ('job__title', 'user__username')
