from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Job(models.Model):
	title = models.CharField(max_length=255)
	company = models.CharField(max_length=255, blank=True)
	location = models.CharField(max_length=255, blank=True)
	description = models.TextField(blank=True)
	posted_at = models.DateTimeField(default=timezone.now)
	# Optional geographic coordinates (latitude, longitude)
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	# Salary range (optional)
	salary_min = models.IntegerField(null=True, blank=True)
	salary_max = models.IntegerField(null=True, blank=True)
	# Visa sponsorship options: none, sponsorship available
	VISA_CHOICES = [
		('none', 'None'),
		('sponsor', 'Sponsorship available'),
	]
	visa_sponsorship = models.CharField(max_length=32, choices=VISA_CHOICES, default='none')
	owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="jobs", null=True, blank=True)

	def __str__(self):
		return f"{self.title} @ {self.company or 'Unknown'}"


class Application(models.Model):
	STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('review', 'In Review'),
        ('interview', 'Interview'),
        ('offer', 'Offer'),
        ('closed', 'Closed'),
    ]
	job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	cover_letter_text = models.TextField(blank=True)
	cover_letter_file = models.FileField(upload_to='applications/', blank=True, null=True)
	submitted_at = models.DateTimeField(default=timezone.now)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="applied")
	# Applicant-provided location (optional) to help map applicants or preferred location
	applicant_location = models.CharField(max_length=255, blank=True)
	applicant_latitude = models.FloatField(null=True, blank=True)
	applicant_longitude = models.FloatField(null=True, blank=True)

	def __str__(self):
		return f"{self.user.username} - {self.job.title} ({self.status})"
