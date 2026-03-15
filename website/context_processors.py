from .models import OwnerNotification


def owner_notifications_context(request):
    if not request.user.is_authenticated:
        return {
            "nav_unread_notification_count": 0,
            "nav_recent_notifications": [],
        }

    recent = list(
        OwnerNotification.objects.filter(user=request.user)
        .order_by("-created_at")[:8]
    )
    unread_count = OwnerNotification.objects.filter(user=request.user, is_read=False).count()

    return {
        "nav_unread_notification_count": unread_count,
        "nav_recent_notifications": recent,
    }
