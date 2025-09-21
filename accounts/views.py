from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Profile
from .forms import ProfileForm
from .forms import SignUpForm
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.urls import reverse


@login_required
def edit_profile(request):
	profile, created = Profile.objects.get_or_create(user=request.user)
	if request.method == 'POST':
		form = ProfileForm(request.POST, request.FILES, instance=profile)
		if form.is_valid():
			# Save profile fields
			form.instance.user = request.user
			profile = form.save()
			# If email field present, update the User model
			email = form.cleaned_data.get('email')
			if email and email != request.user.email:
				request.user.email = email
				request.user.save()
			return redirect('accounts:profile_detail', username=request.user.username)
	else:
		# Prefill email with the user's current email
		initial = {'email': request.user.email}
		form = ProfileForm(instance=profile, initial=initial)
	return render(request, 'accounts/profile_form.html', {'form': form, 'profile': profile})


def profile_detail(request, username):
	from django.contrib.auth import get_user_model

	User = get_user_model()
	user = get_object_or_404(User, username=username)
	profile = None
	try:
		profile = user.profile
	except Profile.DoesNotExist:
		profile = None
	return render(request, 'accounts/profile_detail.html', {'profile': profile, 'profile_user': user})


def signup(request):
	if request.method == 'POST':
		form = SignUpForm(request.POST)
		if form.is_valid():
			user = form.save()
			# Create initial profile fields from signup form
			is_recruiter = form.cleaned_data.get('is_recruiter', False)
			company = form.cleaned_data.get('company', '')
			Profile.objects.create(user=user, is_recruiter=is_recruiter, company=company)
			# Optionally log the user in immediately
			login(request, user)
			return redirect('accounts:profile_detail', username=user.username)
	else:
		form = SignUpForm()
	return render(request, 'registration/signup.html', {'form': form})


class CustomLoginView(LoginView):
	template_name = 'registration/login.html'

	def get_success_url(self):
		# After login redirect to the user's profile detail
		user = self.request.user
		try:
			return reverse('accounts:profile_detail', kwargs={'username': user.username})
		except Exception:
			return super().get_success_url()
