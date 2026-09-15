from .models import Announcement, AnnouncementView


def marketing_updates(request):
    """
    Supplies the notification bell with recent Marketing announcements/events and
    a per-user unread count (simple 'last seen' model). Null-safe for anonymous
    users so it never breaks a page.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'marketing_updates': [],
            'marketing_updates_count': 0,
        }

    active = Announcement.objects.filter(is_active=True).select_related('created_by')

    view = AnnouncementView.objects.filter(user=user).first()
    last_seen = view.last_seen_at if view else None
    if last_seen:
        unread_count = active.filter(created_at__gt=last_seen).count()
    else:
        unread_count = active.count()

    type_labels = dict(Announcement.TYPE_CHOICES)
    items = []
    for ann in active.order_by('-created_at')[:5]:
        is_new = (last_seen is None) or (ann.created_at > last_seen)
        items.append({
            'title': ann.title,
            'type_label': type_labels.get(ann.announcement_type, 'Update'),
            'badge_class': ann.badge_class,
            'event_date': ann.event_date,
            'timestamp': ann.created_at,
            'is_new': is_new,
        })

    return {
        'marketing_updates': items,
        'marketing_updates_count': unread_count,
    }
