# Real-Time Queue Dashboard - Implementation Guide

## Overview
The Queue view has been updated to function as a real-time monitoring dashboard with automatic updates whenever there are new appointments, status changes, or completed services. 

## Current Implementation (Polling-based)

The current implementation uses **polling** to check for queue updates every 3 seconds. This is the default approach that works out-of-the-box without additional dependencies.

### Features:
- ✅ Auto-refreshes queue every 3 seconds
- ✅ Displays current queue status, active patients, and waiting count
- ✅ Shows confirmed, pending, and completed appointments
- ✅ Live indicator showing connection status
- ✅ Manual refresh button
- ✅ Toggle for auto-refresh
- ✅ Animations for appointment status changes
- ✅ Responsive design for all screen sizes

### How It Works:
1. JavaScript makes AJAX requests to `/accounts/appointments/queue-data/?date=YYYY-MM-DD`
2. The view returns JSON with current appointment data and statistics
3. Dashboard updates the DOM with the latest information
4. Updates occur every 3 seconds by default

### Configuration:
To change the update interval, edit line 120 in `appointment_queue.html`:
```javascript
this.updateInterval = 3000; // Change this value (in milliseconds)
```

## Optional: Advanced Setup with Django Channels (WebSocket)

For true real-time updates using WebSockets, follow these steps:

### Prerequisites:
- Windows/Linux/Mac
- Django 6.0.2+
- Python 3.9+

### Step 1: Install Django Channels
```bash
pip install channels channels-redis daphne
```

### Step 2: Update `pawmily/settings.py`

Add to `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    'daphne',  # Add this first
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'website',
]
```

Update `ASGI_APPLICATION`:
```python
ASGI_APPLICATION = 'pawmily.asgi.application'
```

Add Channel Layers configuration:
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('localhost', 6379)],  # Or your Redis server address
        },
    }
}
```

Default timeout (in seconds):
```python
CHANNEL_LAYER_TIMEOUT = 5
```

### Step 3: Update `pawmily/asgi.py`

Replace the entire contents with:
```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from accounts.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pawmily.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
```

### Step 4: Add Signal Handler for Real-Time Broadcasts

Create `accounts/signals.py`:
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Appointment

@receiver(post_save, sender=Appointment)
def appointment_status_changed(sender, instance, created, **kwargs):
    """
    Signal handler that broadcasts appointment status changes to all 
    connected WebSocket clients watching this queue date.
    """
    channel_layer = get_channel_layer()
    queue_group_name = f'queue_{instance.appointment_date.isoformat()}'
    
    async_to_sync(channel_layer.group_send)(
        queue_group_name,
        {
            'type': 'queue_status_changed',
            'appointment_id': instance.id,
            'status': instance.status,
            'status_display': instance.get_status_display(),
        }
    )

# Register the signal in apps.py
```

Update `accounts/apps.py`:
```python
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    
    def ready(self):
        import accounts.signals  # Import signals when app is ready
```

### Step 5: Running with Django Channels

Instead of using the development server, run:
```bash
daphne -b 0.0.0.0 -p 8000 pawmily.asgi:application
```

Or for production:
```bash
daphne -b 0.0.0.0 -p 8000 --access-log - pawmily.asgi:application
```

### Step 6: WebSocket Connection in JavaScript

Update the JavaScript in `appointment_queue.html` to use WebSockets:

```javascript
class QueueWebSocketDashboard {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const currentDate = new Date().toISOString().split('T')[0];
        
        this.ws = new WebSocket(
            `${protocol}//${window.location.host}/ws/queue/?date=${currentDate}`
        );

        this.ws.onopen = () => this.onWebSocketOpen();
        this.ws.onmessage = (event) => this.onWebSocketMessage(event);
        this.ws.onclose = () => this.onWebSocketClose();
        this.ws.onerror = (error) => this.onWebSocketError(error);
    }

    onWebSocketOpen() {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.updateLiveIndicator(true);
        
        // Request initial queue data
        this.ws.send(JSON.stringify({
            action: 'refresh'
        }));
    }

    onWebSocketMessage(event) {
        const message = JSON.parse(event.data);
        
        if (message.type === 'queue_update') {
            this.updateDashboard(message.data);
        } else if (message.type === 'appointment_status_changed') {
            this.updateAppointmentStatus(message);
        }
    }

    onWebSocketClose() {
        console.log('WebSocket disconnected');
        this.updateLiveIndicator(false);
        this.attemptReconnect();
    }

    onWebSocketError(error) {
        console.error('WebSocket error:', error);
        this.updateLiveIndicator(false);
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            console.log(`Reconnecting in ${delay}ms...`);
            
            setTimeout(() => this.connectWebSocket(), delay);
        }
    }

    updateAppointmentStatus(message) {
        const card = document.querySelector(`[data-apt-id="${message.appointment_id}"]`);
        if (card) {
            // Update status badge
            const statusBadge = card.querySelector('.apt-status-badge');
            if (statusBadge) {
                statusBadge.textContent = message.status_display;
                statusBadge.className = `apt-status-badge ${message.status}`;
            }
            
            // Trigger animation
            card.style.opacity = '0.7';
            setTimeout(() => {
                card.style.opacity = '1';
            }, 200);
        }
    }

    // ... rest of the methods from QueueDashboard
}
```

## Redis Setup

If you don't have Redis installed:

### On Windows (using WSL):
```bash
# Install in WSL Windows Subsystem for Linux
sudo apt-get install redis-server
sudo service redis-server start
```

### Using Docker:
```bash
docker run -d -p 6379:6379 redis:latest
```

### Using Python Redis Server (no installation):
```bash
pip install redis
python -m redis.server
```

## Performance Considerations

### Polling (Current)
- **Pros**: Works out-of-the-box, simple to understand
- **Cons**: Higher server load, slightly delayed updates
- **Best for**: Private/internal dashboards with <50 concurrent users

### WebSockets (Advanced)
- **Pros**: True real-time, efficient, professional
- **Cons**: Requires additional setup and dependencies
- **Best for**: Production deployments, public-facing dashboards

## Monitoring and Debugging

### Check Queue Data Endpoint:
```
GET http://localhost:8000/accounts/appointments/queue-data/?date=2024-03-04
```

### Monitor WebSocket Connections:
Add logging to `accounts/consumers.py`:
```python
import logging
logger = logging.getLogger(__name__)

class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f'Client {self.channel_name} connected to {self.queue_group_name}')
        # ... rest of connect method
```

## Troubleshooting

### Queue not updating:
1. Check browser console for JavaScript errors
2. Verify that `/accounts/appointments/queue-data/` endpoint is accessible
3. Ensure auto-refresh toggle is enabled
4. Check network tab in browser developer tools

### WebSocket connection failed:
1. Ensure Daphne is running (not Django dev server)
2. Check Redis is running: `redis-cli ping` (should return PONG)
3. Verify ASGI_APPLICATION is set in settings.py
4. Check firewall allows WebSocket connections

### Database errors:
1. Ensure migrations are applied: `python manage.py migrate`
2. Check database connection settings
3. Verify user has proper permissions

## API Endpoints

### GET /accounts/appointments/queue-data/
Returns current queue data in JSON format.

**Parameters:**
- `date` (optional): YYYY-MM-DD format, defaults to today

**Response:**
```json
{
  "appointments": [
    {
      "id": 1,
      "pet_name": "Buddy",
      "owner_name": "John Doe",
      "time": "14:30",
      "time_ampm": "02:30 PM",
      "status": "confirmed",
      "status_display": "Confirmed",
      "emoji": "🐶",
      "reason": "Checkup"
    }
  ],
  "stats": {
    "date": "2024-03-04",
    "total_appointments": 5,
    "confirmed": 3,
    "pending": 1,
    "completed": 1,
    "active": 4,
    "waiting": 1
  },
  "timestamp": "2024-03-04T14:30:45.123456Z"
}
```

## Security Notes

1. **Authentication**: Both polling and WebSocket require user authentication
2. **Data Privacy**: Users only see appointments they own or manage
3. **Rate Limiting**: Consider adding rate limiting to the queue-data endpoint
4. **CORS**: WebSocket connections are same-origin by default

## Testing

Test the real-time updates:
1. Open the queue in a browser tab
2. Change an appointment status in admin panel in another tab
3. Verify queue updates automatically in the first tab

## Future Enhancements

- WebSocket authentication with tokens
- Connection pooling for better performance
- Caching of queue data
- Sound/desktop notifications for status changes
- Email notifications to pet owners
- Integration with SMS alerts
- Dashboard for staff to see their own queues
- Historical data and analytics
