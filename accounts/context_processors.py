def user_profile(request):
    """Adds `user_profile` to the template context (Profile instance or None)."""
    user = getattr(request, 'user', None)
    profile = None
    if user and user.is_authenticated:
        try:
            profile = user.profile
        except Exception:
            profile = None
    return {'user_profile': profile}
