from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Profile
from .forms import ProfileForm
from .forms import SignUpForm
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.db.models import Q
from django.http import HttpResponseForbidden
import re
from django.contrib.auth.models import User
from django.contrib import messages
from .emails import send_profile_message, send_direct_email
from jobs.models import SavedProfile, Message

@login_required
def message_user_view(request, pk):
    """Compose a message to a user (GET shows form, POST saves Message and sends email)."""
    recipient = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        message_text = request.POST.get("message", "").strip()
        if not message_text:
            messages.error(request, "Please enter a message before sending.")
            return redirect("accounts:message_user", pk=recipient.pk)
        # Save in-app message
        Message.objects.create(sender=request.user, recipient=recipient, subject=subject, body=message_text)
        # Send email notification (keeps existing behavior)
        sent = send_profile_message(request.user, recipient, f"{subject}\n\n{message_text}" if subject else message_text)
        if sent:
            messages.success(request, "Your message has been sent!")
        else:
            messages.success(request, "Message saved. Recipient has no email address so no email was sent.")
        return redirect("accounts:profile_detail", username=recipient.username)

    # GET: render compose form
    return render(request, "accounts/message_user.html", {"recipient": recipient})

@login_required
def email_user_view(request, pk):
    """Recruiter-only: compose and send a real email to an applicant's email address."""
    recipient = get_object_or_404(User, pk=pk)

    # Prevent emailing self
    if request.user == recipient:
        messages.error(request, "You cannot email yourself.")
        return redirect("accounts:profile_detail", username=recipient.username)

    # Ensure the sender is a recruiter
    viewer_profile = getattr(request.user, "profile", None)
    if not viewer_profile or not getattr(viewer_profile, "is_recruiter", False):
        return HttpResponseForbidden("Only recruiters may send emails to applicants.")

    # Optionally prevent emailing other recruiters (intended for applicants)
    try:
        rprof = recipient.profile
        if getattr(rprof, "is_recruiter", False):
            messages.error(request, "This action is intended for contacting applicants.")
            return redirect("accounts:profile_detail", username=recipient.username)
    except Exception:
        # recipient may not have a profile; allow sending if they have an email
        pass

    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        if not body:
            messages.error(request, "Please enter a message before sending.")
            return redirect("accounts:email_user", pk=recipient.pk)

        sent = send_direct_email(request.user, recipient, subject, body)
        if sent:
            display = recipient.get_full_name() or recipient.username
            messages.success(request, f"Email sent to {display}.")
        else:
            messages.error(request, "Failed to send email. The recipient may not have an email address or the email service is not configured.")
        return redirect("accounts:profile_detail", username=recipient.username)

    return render(request, "accounts/email_user.html", {"recipient": recipient})

@login_required
def save_profile_view(request, pk):
    """Allow recruiters to save/unsave a user's profile. Redirect to saved list."""
    target_user = get_object_or_404(User, pk=pk)

    # Ensure viewer is authenticated recruiter (not the profile owner)
    if not request.user.is_authenticated or request.user == target_user:
        messages.error(request, "Not allowed.")
        return redirect('accounts:profile_detail', username=target_user.username)

    # Verify viewer is a recruiter
    viewer_profile = getattr(request.user, "profile", None)
    if not viewer_profile or not getattr(viewer_profile, "is_recruiter", False):
        return HttpResponseForbidden("Only recruiters may save profiles.")

    # Toggle saved state
    obj, created = SavedProfile.objects.get_or_create(recruiter=request.user, saved_user=target_user)
    if not created:
        # already saved -> unsave
        obj.delete()
        messages.success(request, f"Unsaved {target_user.username}.")
    else:
        messages.success(request, f"Saved {target_user.username} to your list.")

    # Redirect recruiter to their saved profiles page
    return redirect('accounts:saved_profiles')

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

	# Determine whether the current viewer should be treated as a recruiter.
	# Owner always sees full profile; anonymous and non-recruiter viewers see full profile.
	# Only other authenticated users who are recruiters are considered viewer recruiters.
	viewer_is_recruiter = False
	if request.user.is_authenticated and request.user != user:
		try:
			viewer_profile = request.user.profile
			viewer_is_recruiter = bool(getattr(viewer_profile, 'is_recruiter', False))
		except Profile.DoesNotExist:
			viewer_is_recruiter = False

	# Determine whether current viewer (if recruiter) has saved this profile
	is_saved = False
	if request.user.is_authenticated and viewer_is_recruiter:
		is_saved = SavedProfile.objects.filter(recruiter=request.user, saved_user=user).exists()

	return render(request, 'accounts/profile_detail.html', {
		'profile': profile,
		'profile_user': user,
		'viewer_is_recruiter': viewer_is_recruiter,
		'is_saved': is_saved,
	})


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


@login_required
def find_applicants(request):
	"""Recruiter-only: unified search across candidate fields using a single query string."""
	profile = getattr(request.user, 'profile', None)
	if not profile or not profile.is_recruiter:
		return HttpResponseForbidden("You are not authorized.")

	# Unified query param
	q = request.GET.get('q', '').strip()

	qs = Profile.objects.filter(is_recruiter=False)

	if q:
		# Tokenize on commas/whitespace; require each token to match at least one field
		tokens = [t for t in re.split(r'[,\s]+', q) if t]
		for t in tokens:
			qs = qs.filter(
				Q(user__username__icontains=t) |
				Q(user__first_name__icontains=t) |
				Q(user__last_name__icontains=t) |
				Q(headline__icontains=t) |
				Q(bio__icontains=t) |
				Q(skills__icontains=t) |
				Q(experience__icontains=t) |
				Q(education__icontains=t) |
				Q(company__icontains=t) |
				Q(location__icontains=t) |
				Q(desired_positions__icontains=t) |
				Q(desired_companies__icontains=t)
			)

	qs = qs.select_related('user').order_by('user__username')

	for p in qs:
		p.skill_list = [s.strip() for s in p.skills.split(",")] if p.skills else []
		p.desired_positions_list = [s.strip() for s in p.desired_positions.split(",")] if p.desired_positions else []

	return render(request, 'accounts/find-candidates.html', {
		'profiles': qs,
		'q': q,
	})

class CustomLoginView(LoginView):
	template_name = 'registration/login.html'

	def get_success_url(self):
		# After login redirect to the user's profile detail
		user = self.request.user
		try:
			return reverse('accounts:profile_detail', kwargs={'username': user.username})
		except Exception:
			return super().get_success_url()

@login_required
def saved_profiles(request):
	"""List of profiles the logged-in recruiter has saved."""
	# ensure recruiter
	profile = getattr(request.user, "profile", None)
	if not profile or not getattr(profile, "is_recruiter", False):
		return HttpResponseForbidden("Not authorized")

	entries = SavedProfile.objects.filter(recruiter=request.user).select_related('saved_user').order_by('-saved_at')

	# Build a list of minimal data for templating (avoid heavy DB lookups)
	result = []
	for e in entries:
		u = e.saved_user
		# attempt to get profile (may not exist)
		try:
			uprof = u.profile
		except Exception:
			uprof = None
		result.append({
			'user': u,
			'profile': uprof,
			'saved_at': e.saved_at,
		})

	return render(request, 'accounts/saved_profiles.html', {'entries': result})

@login_required
def messages_inbox(request):
    """Simple inbox showing messages sent to the logged-in user."""
    msgs = Message.objects.filter(recipient=request.user).select_related("sender").order_by("-sent_at")
    return render(request, "accounts/messages_list.html", {"messages": msgs})

@login_required
def message_detail(request, pk):
    """
    View a single message (recipient only). Mark as read. Allow reply via POST (creates Message and emails).
    """
    msg = get_object_or_404(Message, pk=pk)
    # only recipient or sender may view (basic protective check)
    if request.user != msg.recipient and request.user != msg.sender:
        return HttpResponseForbidden("Not authorized to view this message.")

    # Mark read if recipient views it
    if request.user == msg.recipient and not msg.read:
        msg.read = True
        msg.save(update_fields=["read"])

    if request.method == "POST":
        # reply form: create new message from current user to the other party
        reply_text = request.POST.get("reply", "").strip()
        reply_subject = request.POST.get("subject", "").strip() or f"Re: {msg.subject}" if msg.subject else f"Re:"
        if not reply_text:
            messages.error(request, "Please enter a reply message.")
            return redirect("accounts:message_detail", pk=msg.pk)
        recipient_user = msg.sender if request.user == msg.recipient else msg.recipient
        Message.objects.create(sender=request.user, recipient=recipient_user, subject=reply_subject, body=reply_text)
        send_profile_message(request.user, recipient_user, f"{reply_subject}\n\n{reply_text}")
        messages.success(request, "Reply sent.")
        return redirect("accounts:messages_inbox")

    return render(request, "accounts/message_detail.html", {"message": msg})

