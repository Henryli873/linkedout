from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Job, Application
from django import forms


def search(request):
	# Collect query params
	q = request.GET.get('q', '')
	location = request.GET.get('location', '')
	salary_min = request.GET.get('salary_min', '')
	salary_max = request.GET.get('salary_max', '')
	work_type = request.GET.get('work_type', '')
	visa = request.GET.get('visa_sponsorship', '')

	# Placeholder: in future, you'd query Job model. For now echo the filters.
	context = {
		'q': q,
		'location': location,
		'salary_min': salary_min,
		'salary_max': salary_max,
		'work_type': work_type,
		'visa': visa,
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
