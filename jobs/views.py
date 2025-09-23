from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Job, Application
from .forms import JobPostForm
from django import forms
from django.http import HttpResponseForbidden
from django.db.models import Case, When, Value, IntegerField, F, Q
from django.http import JsonResponse
from django.core.cache import cache
try:
	import requests
except Exception:
	requests = None
import urllib.parse
import urllib.request
import json
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from math import radians, cos, sin, asin, sqrt
import re


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

    # Parse radius/lat/lon
    radius = request.GET.get('radius', '').strip()
    lat = request.GET.get('lat', '').strip()
    lon = request.GET.get('lon', '').strip()
    try:
        radius_f = float(radius) if radius != '' else None
        lat_f = float(lat) if lat != '' else None
        lon_f = float(lon) if lon != '' else None
    except (ValueError, TypeError):
        radius_f = lat_f = lon_f = None

    # Default result container
    context_jobs = qs

    # If radius is not provided (Any), ignore location data and only use name-based filtering
    if radius_f is None:
        if q:
            # Name match = title OR company (no location constraints)
            context_jobs = qs.filter(Q(title__icontains=q) | Q(company__icontains=q)).order_by('-posted_at')
        else:
            # No q and radius Any -> recent first, ignore any location inputs
            context_jobs = qs.order_by('-posted_at')
    else:
        # radius is numeric — ensure we have center coordinates
        if (lat_f is None or lon_f is None) and location:
            geoc = geocode_address(location)
            if geoc:
                lat_f, lon_f = geoc

        # If still no center coords, we cannot apply a distance filter -> return no results
        if lat_f is None or lon_f is None:
            context_jobs = Job.objects.none()
        else:
            # Candidate jobs (do not exclude jobs missing coords yet)
            qs_candidates = qs
            if q:
                qs_candidates = qs_candidates.filter(Q(title__icontains=q) | Q(company__icontains=q))

            nearby_ids = []
            distances = {}

            for job in qs_candidates:
                # job location string (adjust field name if your model uses a different field)
                job_loc_str = getattr(job, 'location', None) or getattr(job, 'location_name', None)
                lat_j, lon_j = job.latitude, job.longitude

                # If coords missing, attempt geocode (cached + persisted)
                if lat_j is None or lon_j is None:
                    if not job_loc_str:
                        # no address available to geocode
                        continue

                    # safe cache key
                    cache_key = f"geocode:job:{job.pk}:{urllib.parse.quote_plus(job_loc_str)}"
                    cached = cache.get(cache_key)
                    if cached and cached.get('lat') is not None and cached.get('lon') is not None:
                        lat_j, lon_j = cached['lat'], cached['lon']
                        # persist to DB if needed
                        try:
                            if job.latitude != lat_j or job.longitude != lon_j:
                                job.latitude = float(lat_j)
                                job.longitude = float(lon_j)
                                job.save(update_fields=['latitude', 'longitude'])
                        except Exception:
                            # ignore db save errors (you can log here)
                            pass
                    else:
                        geoc = geocode_address(job_loc_str)
                        if geoc:
                            lat_j, lon_j = geoc
                            cache.set(cache_key, {'lat': lat_j, 'lon': lon_j}, 60*60*24)
                            try:
                                job.latitude = float(lat_j)
                                job.longitude = float(lon_j)
                                job.save(update_fields=['latitude', 'longitude'])
                            except Exception:
                                pass
                        else:
                            # could not geocode this job -> skip it
                            continue

                # Now compute distance. (Kept your existing haversine signature/order)
                try:
                    d = haversine(lon_f, lat_f, lon_j, lat_j)
                except Exception:
                    # skip any job that raises during distance calc
                    continue

                if d <= radius_f:
                    nearby_ids.append(job.pk)
                    distances[job.pk] = d

            # Build final result set
            if nearby_ids:
                qs_filtered = qs.filter(pk__in=nearby_ids)
                # produce a list sorted by computed distance
                jobs_list = list(qs_filtered)
                jobs_list.sort(key=lambda j: distances.get(j.pk, float('inf')))
                context_jobs = jobs_list
            else:
                context_jobs = Job.objects.none()

    context = {
        'q': q,
        'location': location,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'work_type': work_type,
        'visa': visa,
        'jobs': context_jobs,
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

			# If a location string was provided but lat/lon missing, attempt server-side geocode
			if app.applicant_location and not (app.applicant_latitude and app.applicant_longitude):
				q = app.applicant_location.strip()
				cache_key = f"geocode:app:{q}"
				cached = cache.get(cache_key)
				if cached:
					app.applicant_latitude = cached.get('lat')
					app.applicant_longitude = cached.get('lon')
				else:
					# Use Nominatim for server-side geocoding (respect usage policy in production)
					try:
						url = 'https://nominatim.openstreetmap.org/search'
						resp = requests.get(url, params={'format':'json', 'q': q, 'limit': 1}, headers={'User-Agent':'linkedout/1.0'})
						if resp.status_code == 200:
							data = resp.json()
							if data:
								place = data[0]
								lat = float(place.get('lat'))
								lon = float(place.get('lon'))
								app.applicant_latitude = lat
								app.applicant_longitude = lon
								# cache result for 24 hours
								cache.set(cache_key, {'lat': lat, 'lon': lon}, 60*60*24)
					except Exception:
						# fallback: leave coords empty
						pass
			app.save()
			return redirect('jobs:apply_thanks')
	else:
		form = ApplicationForm()
	return render(request, 'jobs/job_apply.html', {'job': job, 'form': form})


def apply_thanks(request):
	return render(request, 'jobs/apply_thanks.html')

@login_required
def my_applications(request):
    """Candidate sees their own applications."""
    apps = Application.objects.filter(user=request.user).select_related("job")
    return render(request, "jobs/my_applications.html", {"applications": apps})


@login_required
def application_details(request, pk):
    """Candidate sees details of their application."""
    app = get_object_or_404(Application, pk=pk, user=request.user)
    return render(request, "jobs/application_details.html", {"application": app})


@login_required
def recruiter_applications(request):
    """Recruiters see applications for their company postings."""
    if not request.user.is_recruiter:
        return HttpResponseForbidden("You are not authorized.")

    # Assuming recruiter's company is stored in their profile/username for now:
    apps = Application.objects.filter(job__company__icontains=request.user.username).select_related("job", "user")
    return render(request, "jobs/recruiter_applications.html", {"applications": apps})


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status"]


@login_required
def update_application_status(request, pk):
    """Recruiter updates status of an application."""
    if not request.user.is_recruiter:
        return HttpResponseForbidden("Not allowed")

    app = get_object_or_404(Application, pk=pk)

    if request.method == "POST":
        form = ApplicationStatusForm(request.POST, instance=app)
        if form.is_valid():
            form.save()
            return redirect("jobs:recruiter_applications")
    else:
        form = ApplicationStatusForm(instance=app)

    return render(request, "jobs/update_status.html", {"form": form, "application": app})


def interactive_map(request):
	# Renders the map page. Frontend will call the `jobs_nearby` endpoint.
	return render(request, 'jobs/interactive_map.html')


@login_required
def post_job(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_recruiter:
        return redirect('home:index')

    if request.method == 'POST':
        form = JobPostForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.owner = request.user   # ✅ add this line
            job.save()
            return redirect('jobs:job_detail', pk=job.pk)
    else:
        form = JobPostForm()
    return render(request, 'jobs/post_job.html', {'form': form})



@login_required
def my_postings(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_recruiter:
        return redirect('home:index')

    qs = Job.objects.filter(owner=request.user)   # ✅ simple, reliable
    return render(request, 'jobs/my_postings.html', {'jobs': qs})



@login_required
def edit_post(request, pk):
    job = get_object_or_404(Job, pk=pk)
    profile = getattr(request.user, 'profile', None)

    if not profile or not profile.is_recruiter:
        return redirect('home:index')

    # ✅ Owner check using the job.owner field
    if job.owner != request.user:
        return HttpResponseForbidden('You may only edit your own postings')

    if request.method == 'POST':
        form = JobPostForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            return redirect('jobs:job_detail', pk=job.pk)
    else:
        form = JobPostForm(instance=job)

    return render(request, 'jobs/edit_post.html', {'form': form, 'job': job})




def haversine(lat1, lon1, lat2, lon2):
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


def geocode_address(q):
    """
    Return (lat, lon) for an address string or None if lookup fails.
    Tries multiple cleaned variants of the address to improve match success.
    """
    if not q:
        return None

    headers = {'User-Agent': 'linkedout/1.0'}
    q = q.strip()

    # Candidate variants
    candidates = [q]

    # Strip suite/apt/unit markers
    stripped = re.sub(r'\b(?:suite|ste|apt|unit|#)\.?\s*\w+\b', '', q, flags=re.I).strip()
    if stripped and stripped != q:
        candidates.append(stripped)

    # Add ", United States"
    candidates.append(q + ', United States')
    if stripped:
        candidates.append(stripped + ', United States')

    # Use last two comma-separated parts ("City, ST ZIP")
    parts = [p.strip() for p in q.split(',') if p.strip()]
    if len(parts) >= 2:
        tail = ', '.join(parts[-2:])
        candidates.append(tail)
        candidates.append(tail + ', United States')

    # Deduplicate while preserving order
    seen, final_candidates = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            final_candidates.append(c)

    # Try each candidate
    for candidate in final_candidates:
        try:
            if 'requests' in globals() and requests:
                resp = requests.get(
                    'https://nominatim.openstreetmap.org/search',
                    params={'format': 'json', 'q': candidate, 'limit': 1},
                    headers=headers, timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return float(data[0]['lat']), float(data[0]['lon'])
        except Exception:
            pass

        try:
            url = 'https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + urllib.parse.quote(candidate)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as r:
                raw = r.read().decode('utf-8')
                data = json.loads(raw)
                if data:
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception:
            pass

    return None
