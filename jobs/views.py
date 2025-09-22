from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Job, Application
from django import forms
from django.http import HttpResponseForbidden
from django.db.models import Case, When, Value, IntegerField, F


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
		fields = ('cover_letter_text', 'cover_letter_file')
		widgets = {
			'cover_letter_text': forms.Textarea(attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'Type a cover letter (optional)'}),
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
