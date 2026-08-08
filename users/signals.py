"""
Signal handlers for authentication audit logging and brute force protection.
Compliant with Data Privacy Act of 2012 (R.A. 10173) — logs all failed login attempts.
"""
import logging
from django.conf import settings
from django.contrib.auth.signals import user_login_failed, user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def _get_request_meta(request):
    """Extract IP and user agent from request."""
    ip_address = None
    user_agent = ''
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    return ip_address, user_agent


def is_account_locked(username):
    """
    Check if a username is currently locked due to too many failed attempts.
    Returns (is_locked: bool, minutes_remaining: int).
    """
    from .models import FailedLoginAttempt

    max_attempts = getattr(settings, 'MAX_FAILED_LOGIN_ATTEMPTS', 5)
    window_minutes = getattr(settings, 'FAILED_LOGIN_WINDOW_MINUTES', 15)
    lockout_minutes = getattr(settings, 'ACCOUNT_LOCKOUT_MINUTES', 30)

    window_start = timezone.now() - timedelta(minutes=window_minutes)

    recent_failures = FailedLoginAttempt.objects.filter(
        username__iexact=username,
        timestamp__gte=window_start,
    ).count()

    if recent_failures >= max_attempts:
        # Find the timestamp of the Nth failure to calculate lockout expiry
        nth_failure = (
            FailedLoginAttempt.objects
            .filter(username__iexact=username, timestamp__gte=window_start)
            .order_by('-timestamp')
            .values_list('timestamp', flat=True)
            .first()
        )
        if nth_failure:
            lockout_expires = nth_failure + timedelta(minutes=lockout_minutes)
            remaining = (lockout_expires - timezone.now()).total_seconds() / 60
            if remaining > 0:
                return True, int(remaining) + 1
    return False, 0


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """
    Fired by Django whenever authentication fails (wrong password, non-existent user, etc.).
    Also triggered by allauth when MFA code is invalid.
    """
    from .models import FailedLoginAttempt

    username = (
        credentials.get('username')
        or credentials.get('login')
        or credentials.get('email')
        or 'unknown'
    )

    ip_address, user_agent = _get_request_meta(request)

    # Determine reason
    locked, _ = is_account_locked(username)
    reason = 'account_locked' if locked else 'invalid_credentials'

    try:
        FailedLoginAttempt.objects.create(
            username=username[:150],
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
        )
    except Exception as exc:
        logger.error('Failed to log login attempt for %s: %s', username, exc)

    # Log warning with context
    max_attempts = getattr(settings, 'MAX_FAILED_LOGIN_ATTEMPTS', 5)
    window_minutes = getattr(settings, 'FAILED_LOGIN_WINDOW_MINUTES', 15)
    window_start = timezone.now() - timedelta(minutes=window_minutes)
    recent_count = FailedLoginAttempt.objects.filter(
        username__iexact=username, timestamp__gte=window_start
    ).count()

    logger.warning(
        'Failed login attempt: username=%s ip=%s attempts=%d/%d (window=%dmin)',
        username, ip_address, recent_count, max_attempts, window_minutes,
    )


@receiver(user_logged_in)
def clear_failed_attempts_on_success(sender, request, user, **kwargs):
    """
    On successful login, clear the failed attempt counter for this user.
    This prevents lockout from persisting after a successful authentication.
    """
    from .models import FailedLoginAttempt

    window_minutes = getattr(settings, 'FAILED_LOGIN_WINDOW_MINUTES', 15)
    window_start = timezone.now() - timedelta(minutes=window_minutes)

    # Delete recent failures for this username (resets the counter)
    FailedLoginAttempt.objects.filter(
        username__iexact=user.username,
        timestamp__gte=window_start,
    ).delete()
