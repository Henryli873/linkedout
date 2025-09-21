from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Job, Application
from django import forms
from django.db.models import Case, When, Value, IntegerField, F, Q
from django.http import JsonResponse
from math import radians, cos, sin, asin, sqrt


def search(request):
	# Collect query params
	q = request.GET.get('q', '').strip()
	location = request.GET.get('location', '').strip()
	salary_min = request.GET.get('salary_min', '')
	salary_max = request.GET.get('salary_max', '')
	work_type = request.GET.get('work_type', '')
	visa = request.GET.get('visa_sponsorship', '')
	# Base queryset
	qs = Job.objects.all()

	# Apply location filter if provided
	if location:
		qs = qs.filter(location__icontains=location)

	# If there's a query string, compute a simple relevance rank and order by it
	if q:
		# annotate score parts and sum them
		qs = qs.annotate(
			title_match=Case(When(title__icontains=q, then=Value(3)), default=Value(0), output_field=IntegerField()),
			company_match=Case(When(company__icontains=q, then=Value(2)), default=Value(0), output_field=IntegerField()),
			desc_match=Case(When(description__icontains=q, then=Value(1)), default=Value(0), output_field=IntegerField()),
		).annotate(rank=F('title_match') + F('company_match') + F('desc_match'))

		qs = qs.order_by('-rank', '-posted_at')
	else:
		# default: most recently posted first
		qs = qs.order_by('-posted_at')

	context = {
		'q': q,
		'location': location,
		'salary_min': salary_min,
		'salary_max': salary_max,
		'work_type': work_type,
		'visa': visa,
		'jobs': qs,
	}
	return render(request, 'jobs/search_results.html', context)


def job_detail(request, pk):
	job = get_object_or_404(Job, pk=pk)
	return render(request, 'jobs/job_detail.html', {'job': job})


class ApplicationForm(forms.ModelForm):
	class Meta:
		model = Application
		fields = ('cover_letter_text', 'cover_letter_file', 'applicant_location', 'applicant_latitude', 'applicant_longitude')
		widgets = {
			'cover_letter_text': forms.Textarea(attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'Type a cover letter (optional)'}),
			'applicant_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, State or address'}),
			'applicant_latitude': forms.HiddenInput(),
			'applicant_longitude': forms.HiddenInput(),
		}

	def clean_cover_letter_file(self):
		f = self.cleaned_data.get('cover_letter_file')
		if f:
			# Basic check for PDF
			if not f.name.lower().endswith('.pdf'):
				raise forms.ValidationError('Only PDF uploads are accepted for cover letters.')
		return f


@login_required
def apply(request, pk):
	job = get_object_or_404(Job, pk=pk)
	if request.method == 'POST':
		# If user clicked skip, submit without cover letter
		if 'skip' in request.POST:
			Application.objects.create(job=job, user=request.user)
			return redirect('jobs:apply_thanks')

		form = ApplicationForm(request.POST, request.FILES)
		if form.is_valid():
			app = form.save(commit=False)
			app.job = job
			app.user = request.user
			# applicant lat/lon may be provided via hidden fields populated by client-side geocoding
			app.applicant_location = form.cleaned_data.get('applicant_location', '')
			app.applicant_latitude = form.cleaned_data.get('applicant_latitude')
			app.applicant_longitude = form.cleaned_data.get('applicant_longitude')
			app.save()
			return redirect('jobs:apply_thanks')
	else:
		form = ApplicationForm()
	return render(request, 'jobs/job_apply.html', {'job': job, 'form': form})


def apply_thanks(request):
	return render(request, 'jobs/apply_thanks.html')


def interactive_map(request):
	# Renders the map page. Frontend will call the `jobs_nearby` endpoint.
	return render(request, 'jobs/interactive_map.html')


def haversine(lon1, lat1, lon2, lat2):
	# Calculate the great circle distance in miles between two points
	# on the earth (specified in decimal degrees)
	# convert decimal degrees to radians
	lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
	# haversine formula
	dlon = lon2 - lon1
	dlat = lat2 - lat1
	a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
	c = 2 * asin(sqrt(a))
	miles = 3956 * c
	return miles


def jobs_nearby(request):
	# Returns JSON list of jobs within radius miles of given lat/lon params
	try:
		lat = float(request.GET.get('lat'))
		lon = float(request.GET.get('lon'))
	except (TypeError, ValueError):
		return JsonResponse({'error': 'lat and lon required'}, status=400)

	radius = float(request.GET.get('radius', 15))
	q = request.GET.get('q', '').strip()

	jobs = []
	qs = Job.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
	if q:
		qs = qs.filter(Q(title__icontains=q) | Q(company__icontains=q) | Q(description__icontains=q))

	for job in qs:
		dist = haversine(lon, lat, job.longitude, job.latitude)
		if dist <= radius:
			jobs.append({
				'id': job.pk,
				'title': job.title,
				'company': job.company,
				'location': job.location,
				'lat': job.latitude,
				'lon': job.longitude,
				'distance_miles': round(dist, 2),
			})

	# sort by distance
	jobs.sort(key=lambda x: x['distance_miles'])
	return JsonResponse({'jobs': jobs})
