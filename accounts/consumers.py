import json
from datetime import date
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Appointment


class QueueConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time queue updates.
    Broadcasts queue changes to all connected clients watching the same date.
    """
    
    async def connect(self):
        # Get the date from the query string
        query_string = self.scope.get('query_string', b'').decode()
        self.queue_date = date.today()
        
        if 'date=' in query_string:
            date_str = query_string.split('date=')[1].split('&')[0]
            try:
                self.queue_date = date.fromisoformat(date_str)
            except (ValueError, IndexError):
                pass
        
        # Create a unique group name based on the queue date
        self.queue_group_name = f'queue_{self.queue_date.isoformat()}'
        
        # Join the group
        await self.channel_layer.group_add(
            self.queue_group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(
            self.queue_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Receive message from WebSocket.
        Expected format: {"action": "refresh"}
        """
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'refresh':
                # Send current queue data
                queue_data = await self.get_queue_data()
                await self.send(text_data=json.dumps({
                    'type': 'queue_update',
                    'data': queue_data
                }))
        except json.JSONDecodeError:
            pass

    async def queue_update(self, event):
        """
        Handle queue update messages from the group.
        Called when an appointment status changes.
        """
        # Send the update to the WebSocket
        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'data': event.get('data', {})
        }))

    async def queue_status_changed(self, event):
        """
        Handle individual appointment status changes.
        """
        await self.send(text_data=json.dumps({
            'type': 'appointment_status_changed',
            'appointment_id': event.get('appointment_id'),
            'status': event.get('status'),
            'status_display': event.get('status_display'),
        }))

    @database_sync_to_async
    def get_queue_data(self):
        """Get current queue data for the connected date."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        
        User = get_user_model()
        user = self.scope['user']
        
        if not user.is_authenticated:
            return {'error': 'Not authenticated'}
        
        # Get appointments for the date
        appointments_qs = Appointment.objects.filter(
            appointment_date=self.queue_date,
        ).select_related('owner', 'pet', 'staff').order_by('start_time', 'slot_number')
        
        # Build appointment list
        appointments_data = []
        for apt in appointments_qs:
            # Check if user should see this appointment
            is_staff = hasattr(user, 'profile') and user.profile.role in ['staff', 'manager']
            if not (is_staff or apt.owner_id == user.id):
                continue
            
            pet_emoji = '🐾'
            if apt.pet:
                species_emojis = {
                    'dog': '🐶',
                    'cat': '🐱',
                    'bird': '🐦',
                }
                pet_emoji = species_emojis.get(apt.pet.species, '🐾')
            
            apt_data = {
                'id': apt.id,
                'pet_name': apt.pet.name if apt.pet else 'Walk-in',
                'owner_name': apt.owner.get_full_name() or apt.owner.username,
                'owner_id': apt.owner.id,
                'time': apt.start_time.strftime('%H:%M'),
                'time_ampm': apt.start_time.strftime('%I:%M %p'),
                'status': apt.status,
                'status_display': apt.get_status_display(),
                'type': apt.appointment_type,
                'type_display': apt.get_appointment_type_display(),
                'emoji': pet_emoji,
                'reason': apt.reason or '',
                'slot_number': apt.slot_number,
            }
            appointments_data.append(apt_data)
        
        # Calculate queue statistics
        confirmed_count = appointments_qs.filter(status=Appointment.STATUS_CONFIRMED).count()
        pending_count = appointments_qs.filter(status=Appointment.STATUS_PENDING).count()
        completed_count = appointments_qs.filter(status=Appointment.STATUS_COMPLETED).count()
        active_count = appointments_qs.exclude(
            status__in=[Appointment.STATUS_REJECTED, Appointment.STATUS_CANCELLED, 
                       Appointment.STATUS_COMPLETED]
        ).count()
        waiting_count = appointments_qs.filter(status=Appointment.STATUS_PENDING).count()
        
        queue_stats = {
            'date': self.queue_date.isoformat(),
            'date_display': self.queue_date.strftime('%A, %B %d, %Y'),
            'total_appointments': appointments_qs.count(),
            'confirmed': confirmed_count,
            'pending': pending_count,
            'completed': completed_count,
            'active': active_count,
            'waiting': waiting_count,
        }
        
        return {
            'appointments': appointments_data,
            'stats': queue_stats,
            'timestamp': timezone.now().isoformat(),
        }
