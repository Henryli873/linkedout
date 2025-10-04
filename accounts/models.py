from django.conf import settings
from django.db import models


class Profile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	headline = models.CharField(max_length=200, blank=True)
	bio = models.TextField(blank=True)
	skills = models.TextField(blank=True, help_text="Comma-separated list of skills")
	experience = models.TextField(blank=True, help_text="Work experience / summary")
	education = models.TextField(blank=True)
	github = models.URLField(blank=True)
	linkedin = models.URLField(blank=True)
	website = models.URLField(blank=True)
	# Optional profile location (with optional geocoded coordinates)
	location = models.CharField(max_length=255, blank=True)
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
	# Recruiter flag and company when applicable
	is_recruiter = models.BooleanField(default=False)
	company = models.CharField(max_length=200, blank=True)

	# For job-seekers: desired positions and companies of interest (stored as text lists)
	desired_positions = models.TextField(blank=True, help_text="Comma-separated desired positions")
	desired_companies = models.TextField(blank=True, help_text="Comma-separated desired companies")

	# Contact
	phone = models.CharField(max_length=40, blank=True)

	# Visibility toggles: when a recruiter views the profile they will only see
	# sections the user has chosen to make visible.
	headline_visible = models.BooleanField(default=True)
	bio_visible = models.BooleanField(default=True)
	skills_visible = models.BooleanField(default=True)
	experience_visible = models.BooleanField(default=True)
	education_visible = models.BooleanField(default=True)
	links_visible = models.BooleanField(default=True)
	company_visible = models.BooleanField(default=True)
	desired_positions_visible = models.BooleanField(default=True)
	desired_companies_visible = models.BooleanField(default=True)
	phone_visible = models.BooleanField(default=False)
	email_visible = models.BooleanField(default=False)

	def __str__(self) -> str:
		return f"Profile: {self.user.username}"
