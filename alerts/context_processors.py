def unread_notifications_count(request):
    if not request.user.is_authenticated:
        return {"unread_notifications": 0}
    return {"unread_notifications": request.user.notifications.filter(read_at__isnull=True).count()}
