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


def send_direct_email(sender, recipient, subject, body):
    """
    Send a direct email to the recipient with a custom subject and body.
    Returns True on success, False otherwise.
    """
    if not getattr(recipient, "email", None):
        return False

    sender_name = getattr(sender, "get_full_name", None)
    sender_display = sender.get_full_name() if callable(sender_name) and sender.get_full_name() else getattr(sender, "username", "Someone")

    subj = (subject or "").strip() or f"Message from {sender_display} on LinkedOut"
    body_text = f"{body}\n\n---\nFrom: {sender_display}\nUsername: {getattr(sender, 'username', '')}\nContact email: {getattr(sender, 'email', 'Not provided')}"

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@linkedout.com")

    try:
        email = EmailMessage(subject=subj, body=body_text, from_email=from_email, to=[recipient.email])
        if getattr(sender, "email", None):
            email.reply_to = [sender.email]
            email.extra_headers = {"Reply-To": sender.email}
        email.send(fail_silently=False)
        return True
    except Exception:
        return False
