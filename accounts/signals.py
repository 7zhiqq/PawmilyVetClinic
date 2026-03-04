from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Appointment

@receiver(post_save, sender=Appointment)
def appointment_status_changed(sender, instance, created, update_fields=None, **kwargs):
    """
    Signal handler that broadcasts appointment status changes to all 
    connected WebSocket clients watching this queue date.
    
    This works regardless of whether you're using polling or WebSockets.
    With WebSockets enabled, this will push updates to clients in real-time.
    With polling, clients will receive the update on their next poll.
    """
    if not created and update_fields:
        # Only trigger if status was actually updated
        if 'status' in update_fields:
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer
                
                channel_layer = get_channel_layer()
                queue_group_name = f'queue_{instance.appointment_date.isoformat()}'
                
                # Send to the queue group
                async_to_sync(channel_layer.group_send)(
                    queue_group_name,
                    {
                        'type': 'queue_status_changed',
                        'appointment_id': instance.id,
                        'status': instance.status,
                        'status_display': instance.get_status_display(),
                    }
                )
            except (ImportError, AttributeError):
                # Channels not installed or not configured - that's fine
                # Polling will pick up the change on next refresh
                pass
