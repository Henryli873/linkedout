"""
URL configuration for linkedout project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import CustomLoginView
from . import admin as linkedout_admin

urlpatterns = [
    # Custom export URLs - must be before admin catch-all
    path('admin/export-accounts/', linkedout_admin.export_accounts_csv, name='export-accounts'),
    path('admin/export-auth/', linkedout_admin.export_auth_csv, name='export-auth'),
    path('admin/export-jobs/', linkedout_admin.export_jobs_csv, name='export-jobs'),
    path('admin/export-all/', linkedout_admin.export_all_csv, name='export-all'),
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    # Custom login view (will redirect to profile on success)
    path('accounts/auth/login/', CustomLoginView.as_view(), name='login'),
    # Django built-in auth views (logout/password management and others)
    path('accounts/auth/', include('django.contrib.auth.urls')),
    # Jobs search frontend
    path('search/', include('jobs.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
