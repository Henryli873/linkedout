from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
import csv
from accounts.models import Profile
from django.contrib.auth.models import User
from jobs.models import Job, Application


def export_accounts_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="accounts.csv"'

    writer = csv.writer(response)
    writer.writerow(['Username', 'Email', 'First Name', 'Last Name', 'Headline', 'Bio', 'Skills', 'Experience', 'Education', 'Location', 'Company', 'Is Recruiter'])

    for profile in Profile.objects.select_related('user'):
        writer.writerow([
            profile.user.username,
            profile.user.email,
            profile.user.first_name,
            profile.user.last_name,
            profile.headline,
            profile.bio,
            profile.skills,
            profile.experience,
            profile.education,
            profile.location,
            profile.company,
            profile.is_recruiter,
        ])

    return response


def export_auth_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="auth.csv"'

    writer = csv.writer(response)
    writer.writerow(['Username', 'Email', 'First Name', 'Last Name', 'Is Staff', 'Is Superuser', 'Date Joined', 'Last Login'])

    for user in User.objects.all():
        writer.writerow([
            user.username,
            user.email,
            user.first_name,
            user.last_name,
            user.is_staff,
            user.is_superuser,
            user.date_joined,
            user.last_login,
        ])

    return response


def export_jobs_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jobs.csv"'

    writer = csv.writer(response)
    writer.writerow(['Title', 'Company', 'Location', 'Description', 'Posted At', 'Salary Min', 'Salary Max', 'Visa Sponsorship', 'Owner'])

    for job in Job.objects.select_related('owner'):
        writer.writerow([
            job.title,
            job.company,
            job.location,
            job.description,
            job.posted_at,
            job.salary_min,
            job.salary_max,
            job.visa_sponsorship,
            job.owner.username if job.owner else '',
        ])

    return response


def export_all_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all_data.csv"'

    writer = csv.writer(response)
    writer.writerow(['Type', 'Username', 'Email', 'Title', 'Company', 'Location', 'Description', 'Posted At', 'Status', 'Submitted At'])

    # Export users
    for profile in Profile.objects.select_related('user'):
        writer.writerow([
            'User',
            profile.user.username,
            profile.user.email,
            profile.headline,
            profile.company,
            profile.location,
            profile.bio,
            '',
            '',
            '',
        ])

    # Export jobs
    for job in Job.objects.select_related('owner'):
        writer.writerow([
            'Job',
            job.owner.username if job.owner else '',
            '',
            job.title,
            job.company,
            job.location,
            job.description,
            job.posted_at,
            '',
            '',
        ])

    # Export applications
    for app in Application.objects.select_related('job', 'user'):
        writer.writerow([
            'Application',
            app.user.username,
            '',
            app.job.title,
            app.job.company,
            app.applicant_location,
            app.cover_letter_text,
            '',
            app.status,
            app.submitted_at,
        ])

    return response


class LinkedOutAdminSite(admin.AdminSite):
    site_header = "LinkedOut Administration"
    site_title = "LinkedOut Admin"
    index_title = "Welcome to LinkedOut Admin"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-accounts/', self.admin_view(export_accounts_csv), name='export-accounts'),
            path('export-auth/', self.admin_view(export_auth_csv), name='export-auth'),
            path('export-jobs/', self.admin_view(export_jobs_csv), name='export-jobs'),
            path('export-all/', self.admin_view(export_all_csv), name='export-all'),
        ]
        return custom_urls + urls


# The models are already registered via @admin.register decorators in their respective admin.py files
# No need to register them again here