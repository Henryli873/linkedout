from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Job, Application, SavedProfile
from .forms import JobPostForm
from accounts.models import Profile
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

def calculate_match_score(job, profile):
    """Calculate how well a candidate matches a job posting (0-100)."""
    score = 0
    max_score = 0
    
    # Skills matching (40% of total score)
    skills_weight = 40
    max_score += skills_weight
    if job.description and profile.skills:
        job_text = (job.title + " " + job.description + " " + (job.company or "")).lower()
        candidate_skills = [s.strip().lower() for s in profile.skills.split(",") if s.strip()]
        
        skills_matched = 0
        for skill in candidate_skills:
            if skill in job_text:
                skills_matched += 1
        
        if candidate_skills:
            skills_score = (skills_matched / len(candidate_skills)) * skills_weight
            score += skills_score
    
    # Desired positions matching (25% of total score)
    position_weight = 25
    max_score += position_weight
    if profile.desired_positions and job.title:
        desired_positions = [p.strip().lower() for p in profile.desired_positions.split(",") if p.strip()]
        job_title_lower = job.title.lower()
        
        for position in desired_positions:
            if position in job_title_lower or job_title_lower in position:
                score += position_weight
                break
    
    # Company matching (15% of total score)
    company_weight = 15
    max_score += company_weight
    if profile.desired_companies and job.company:
        desired_companies = [c.strip().lower() for c in profile.desired_companies.split(",") if c.strip()]
        job_company_lower = job.company.lower()
        
        for company in desired_companies:
            if company in job_company_lower or job_company_lower in company:
                score += company_weight
                break
    
    # Location proximity (20% of total score)
    location_weight = 20
    max_score += location_weight
    if profile.latitude and profile.longitude and job.latitude and job.longitude:
        # Calculate distance using haversine formula
        distance_miles = haversine(profile.longitude, profile.latitude, job.longitude, job.latitude)
        if distance_miles <= 50:  # Within 50 miles gets full points
            score += location_weight
        elif distance_miles <= 100:  # 50-100 miles gets half points
            score += location_weight * 0.5
        elif distance_miles <= 200:  # 100-200 miles gets quarter points
            score += location_weight * 0.25
    else:
        # If no coordinates, try text matching
        if profile.location and job.location:
            if profile.location.lower() in job.location.lower() or job.location.lower() in profile.location.lower():
                score += location_weight * 0.7  # 70% of location score for text match
    
    # Return percentage score
    return min(100, (score / max_score) * 100) if max_score > 0 else 0


@login_required
def job_recommendations(request, job_id):
    """Show candidate recommendations for a specific job posting."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
        return HttpResponseForbidden("You are not authorized.")
    
    job = get_object_or_404(Job, pk=job_id, owner=request.user)
    
    # Get all non-recruiter profiles
    candidates = Profile.objects.filter(
        is_recruiter=False,
        user__is_active=True
    ).select_related('user')
    
    # Calculate match scores and filter out low matches
    recommendations = []
    for candidate in candidates:
        # Skip if candidate already applied
        if Application.objects.filter(job=job, user=candidate.user).exists():
            continue
            
        score = calculate_match_score(job, candidate)
        if score >= 20:  # Only show candidates with at least 20% match
            recommendations.append({
                'profile': candidate,
                'score': score,
                'is_saved': SavedProfile.objects.filter(recruiter=request.user, saved_user=candidate.user).exists()
            })
    
    # Sort by score (highest first)
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    # Limit to top 20 recommendations
    recommendations = recommendations[:20]
    
    return render(request, 'jobs/job_recommendations.html', {
        'job': job,
        'recommendations': recommendations,
    })


def job_detail(request, pk):
	job = get_object_or_404(Job, pk=pk)
	user_profile = getattr(request.user, 'profile', None) if request.user.is_authenticated else None
	
	# For recruiters viewing their own jobs, show quick recommendation preview
	recommendation_count = 0
	if (request.user.is_authenticated and user_profile and 
		user_profile.is_recruiter and job.owner == request.user):
		
		candidates = Profile.objects.filter(is_recruiter=False, user__is_active=True)
		for candidate in candidates:
			if Application.objects.filter(job=job, user=candidate.user).exists():
				continue
			score = calculate_match_score(job, candidate)
			if score >= 20:
				recommendation_count += 1
		recommendation_count = min(recommendation_count, 20)  # Cap display
	
	return render(request, 'jobs/job_detail.html', {
		'job': job,
		'user_profile': user_profile,
		'recommendation_count': recommendation_count,
	})

@login_required
def suggest_jobs(request):
    """Suggest jobs based on the logged-in user's skills."""
    profile = getattr(request.user, "profile", None)
    if not profile or profile.is_recruiter:
        # recruiters don’t get suggestions
        return redirect("jobs:search")

    skills_str = profile.skills or ""
    skills = [s.strip() for s in skills_str.split(",") if s.strip()]

    if not skills:
        jobs = Job.objects.none()
    else:
        # Build OR query across all skills
        query = Q()
        for skill in skills:
            # break "Software Engineering" into ["Software", "Engineering"]
            words = skill.split()
            for word in words:
                query |= (
                    Q(title__icontains=word) |
                    Q(description__icontains=word) |
                    Q(company__icontains=word)
                )

        jobs = Job.objects.filter(query).order_by("-posted_at").distinct()

    return render(request, "jobs/suggested_jobs.html", {"jobs": jobs, "skills": skills})


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
    """Recruiters see applications for jobs they posted in a Kanban board."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
        return HttpResponseForbidden("You are not authorized.")

    apps = (
        Application.objects.filter(job__owner=request.user)
        .select_related("job", "user")
        .order_by("status", "-submitted_at")
    )

    status_choices = list(Application.STATUS_CHOICES)

    # Build columns structure for easy templating
    columns = [{"key": key, "label": label, "apps": []} for key, label in status_choices]
    col_index = {c["key"]: c for c in columns}

    for app in apps:
        if app.status in col_index:
            col_index[app.status]["apps"].append(app)
        else:
            # if somehow an unknown status sneaks in, create a catch-all
            if "_unknown" not in col_index:
                columns.append({"key": "_unknown", "label": "Unknown", "apps": []})
                col_index["_unknown"] = columns[-1]
            col_index["_unknown"]["apps"].append(app)

    context = {
        "status_choices": status_choices,
        "columns": columns,
    }
    return render(request, "jobs/recruiter_applications.html", context)


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status"]


@login_required
def update_application_status(request, pk):
    """Recruiter updates status of an application."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
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

@login_required
def recruiter_update_application_status_ajax(request):
    """AJAX endpoint to update application status from Kanban."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
        return JsonResponse({"error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    app_id = request.POST.get("app_id")
    new_status = request.POST.get("status")

    valid_statuses = {k for k, _ in Application.STATUS_CHOICES}
    if not app_id or new_status not in valid_statuses:
        return JsonResponse({"error": "Invalid parameters"}, status=400)

    try:
        app = Application.objects.select_related("job").get(pk=app_id)
    except Application.DoesNotExist:
        return JsonResponse({"error": "Application not found"}, status=404)

    if app.job.owner != request.user:
        return JsonResponse({"error": "Not authorized for this application"}, status=403)

    app.status = new_status
    app.save(update_fields=["status"])

    return JsonResponse({"ok": True, "status": new_status})


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

    jobs = Job.objects.filter(owner=request.user).order_by('-posted_at')
    
    # Add analytics for each job
    jobs_with_analytics = []
    for job in jobs:
        # Count applications
        application_count = Application.objects.filter(job=job).count()
        
        # Count potential candidates (for recommendations)
        candidate_count = 0
        candidates = Profile.objects.filter(is_recruiter=False, user__is_active=True)
        for candidate in candidates:
            # Skip if already applied
            if Application.objects.filter(job=job, user=candidate.user).exists():
                continue
            score = calculate_match_score(job, candidate)
            if score >= 20:  # Same threshold as recommendations
                candidate_count += 1
        
        jobs_with_analytics.append({
            'job': job,
            'application_count': application_count,
            'candidate_count': min(candidate_count, 20),  # Cap at 20 for display
        })
    
    # Calculate overall statistics
    total_jobs = len(jobs_with_analytics)
    total_applications = sum(item['application_count'] for item in jobs_with_analytics)
    total_candidates = sum(item['candidate_count'] for item in jobs_with_analytics)
    
    return render(request, 'jobs/my_postings.html', {
        'jobs_with_analytics': jobs_with_analytics,
        'total_jobs': total_jobs,
        'total_applications': total_applications, 
        'total_candidates': total_candidates,
    })



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


@login_required
def recruiter_job_markers(request):
    """Return the logged-in recruiter's own jobs with existing coordinates (if any)."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
        return JsonResponse({"error": "Not authorized"}, status=403)

    jobs_qs = Job.objects.filter(owner=request.user).order_by("-posted_at")
    data = [
        {
            "id": j.pk,
            "title": j.title,
            "company": j.company,
            "lat": j.latitude,
            "lon": j.longitude,
        }
        for j in jobs_qs
    ]
    return JsonResponse({"jobs": data})


@login_required
def recruiter_set_job_location(request):
    """Allow a recruiter to set latitude/longitude for one of their job postings."""
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
        return JsonResponse({"error": "Not authorized"}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    job_id = None
    lat = None
    lon = None

    # Prefer JSON payload if provided
    if request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body.decode("utf-8"))
            job_id = body.get("job_id")
            lat = body.get("lat")
            lon = body.get("lon")
        except Exception:
            pass

    # Fallback to form-encoded
    if job_id is None:
        job_id = request.POST.get("job_id")
        lat = request.POST.get("lat", lat)
        lon = request.POST.get("lon", lon)

    # Validate target job and ownership
    try:
        job = Job.objects.get(pk=job_id, owner=request.user)
    except (Job.DoesNotExist, ValueError, TypeError):
        return JsonResponse({"error": "Job not found"}, status=404)

    # Validate coordinates
    try:
        lat = float(lat)
        lon = float(lon)
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError("Out-of-range coordinates")
    except Exception:
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    # Persist
    job.latitude = lat
    job.longitude = lon
    job.save(update_fields=["latitude", "longitude"])

    return JsonResponse({"ok": True, "job_id": job.pk, "lat": lat, "lon": lon})


@login_required
def recruiter_applicants(request):
    """Return applicants (with coordinates) for jobs owned by the logged-in recruiter.
    Optional GET param: job_id to filter by a specific job the applicant applied to.
    """
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.is_recruiter:
        return JsonResponse({"error": "Not authorized"}, status=403)

    job_id = request.GET.get("job_id")
    qs = (
        Application.objects.select_related("job", "user")
        .filter(job__owner=request.user)
        .exclude(applicant_latitude__isnull=True)
        .exclude(applicant_longitude__isnull=True)
    )
    if job_id:
        try:
            qs = qs.filter(job__pk=int(job_id))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid job_id"}, status=400)

    apps = []
    for app in qs:
        apps.append({
            "id": app.pk,
            "username": app.user.username,
            "job_id": app.job_id,
            "job_title": app.job.title,
            "lat": app.applicant_latitude,
            "lon": app.applicant_longitude,
            "location": app.applicant_location or "",
            "status": app.status,
            "submitted_at": app.submitted_at.isoformat(),
        })

    return JsonResponse({"applications": apps})
