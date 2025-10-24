from django.conf import settings
from django.core.mail import EmailMessage

def send_profile_message(sender, recipient, message):
    """
    Send a profile message email to recipient.
    Returns True if mail was dispatched, False if recipient has no email or sending failed.
    Sets 'Reply-To' to sender.email when available so recipients can reply directly.
    """
    if not getattr(recipient, "email", None):
        return False

    sender_name = getattr(sender, "get_full_name", None)
    sender_display = sender.get_full_name() if callable(sender_name) and sender.get_full_name() else getattr(sender, "username", "Someone")
    subject = f"Message from {sender_display} on LinkedOut"
    body = f"{message}\n\n---\nFrom: {sender_display}\nUsername: {getattr(sender, 'username', '')}\nContact email: {getattr(sender, 'email', 'Not provided')}"

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@linkedout.com")

    try:
        email = EmailMessage(subject=subject, body=body, from_email=from_email, to=[recipient.email])
        # prefer reply_to attribute (supported by Django EmailMessage)
        if getattr(sender, "email", None):
            email.reply_to = [sender.email]
            # also set extra headers for mail servers that rely on them
            email.extra_headers = {"Reply-To": sender.email}
        email.send(fail_silently=False)
        return True
    except Exception:
        # Sending failed (could log the exception)
        return False
