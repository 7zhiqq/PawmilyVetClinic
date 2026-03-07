# Vaccination and Follow-Up Tracking System

## Overview

The Pawmily Veterinary Clinic has implemented a comprehensive **Vaccination and Follow-Up Tracking System** that automatically monitors and reminds pet owners and staff about upcoming booster vaccinations and follow-up consultations based on medical records.

## Features

### 1. **Automatic Booster Date Calculation**
   - When a vaccination is recorded, the system automatically calculates the next booster date based on the vaccine type's recommended interval
   - Staff can override the calculated date if needed
   - Vaccines are linked to vaccine types that define standard intervals (e.g., annual, 3-year)

### 2. **Vaccination Schedule Tracking**
   - Each vaccination automatically creates a `VaccinationSchedule` record
   - Schedules are categorized by status:
     - **Pending**: Due more than 2 weeks away
     - **Due**: Due within the next 2 weeks
     - **Overdue**: Past the due date
     - **Completed**: Successfully administered
     - **Skipped**: Owner declined or vaccine is no longer needed

### 3. **Follow-Up Reminders**
   - When a medical record includes a follow-up date, a `FollowUpReminder` is automatically created
   - Follow-ups track:
     - Reason for follow-up (e.g., "Monitor wound healing")
     - Scheduled date
     - Status (Pending, Due Soon, Overdue, Completed, Cancelled)
     - Whether appointment was completed

### 4. **Smart Reminder Status**
   - Vaccinations become "Due" when within 14 days of the due date
   - Follow-ups become "Due" when within 7 days of the scheduled date
   - Both automatically mark as "Overdue" when past their date
   - Status updates daily via automated management commands

### 5. **Multi-User Views**
   - **Pet Owners**: See reminders for all their pets on the dashboard and in a dedicated reminders page
   - **Staff**: See all due and overdue reminders across all pets (priority view)
   - **Managers**: Full overview of clinic-wide vaccination and follow-up status

### 6. **Dashboard Integration**
   - Quick glance at upcoming vaccinations and follow-ups
   - Overdue items highlighted in red
   - Due items highlighted in yellow
   - Pending items shown in blue

## Database Models

### VaccineType
Defines vaccine masters with standard booster intervals.

```python
VaccineType
├── name: str (e.g., "Rabies", "DHPP")
├── species: str (dog, cat, bird, other)
├── booster_interval_days: int (recommended days between boosters)
├── description: str
└── is_active: bool
```

### MedicalRecord (Enhanced)
Now includes:
- `follow_up_reason`: Reason for the follow-up visit

### VaccinationRecord (Enhanced)
Now includes:
- `vaccine_type`: ForeignKey to VaccineType for auto-calculation
- Auto-saves next_due_date when saved with a vaccine_type

### VaccinationSchedule (New)
Automatically created and maintained for each vaccination.

```python
VaccinationSchedule
├── pet: ForeignKey
├── vaccination_record: ForeignKey
├── vaccine_type: ForeignKey
├── next_due_date: DateField
├── status: str (pending, due, overdue, completed, skipped)
├── reminder_sent: bool
├── reminder_sent_date: DateTimeField
└── notes: TextField
```

### FollowUpReminder (New)
Automatically created when medical record has a follow-up date.

```python
FollowUpReminder
├── pet: ForeignKey
├── medical_record: ForeignKey
├── follow_up_date: DateField
├── reason: str
├── status: str (pending, due, overdue, completed, cancelled)
├── reminder_sent: bool
├── reminder_sent_date: DateTimeField
├── completed_appointment: ForeignKey (optional)
└── notes: TextField
```

## Usage

### Setting Up Vaccines

1. **Initial Setup**: Seed default vaccine types
   ```bash
   python manage.py seed_vaccines
   ```
   This creates standard vaccines for dogs and cats with typical intervals.

2. **Add Custom Vaccines** (Admin Panel):
   - Go to Django Admin → Records → Vaccine Types
   - Add vaccine with name, species, and booster interval

### Recording Vaccinations

**Staff creates a medical record, then adds vaccination:**

1. Go to Medical Records → Add Medical Record (for a consultation)
2. Click "Add Vaccination" in the medical record
3. Select vaccine type (or enter custom name)
4. Set date administered
5. **Leave "Next Due Date" blank** to auto-calculate, OR set manually
6. Save

**Result**: System automatically:
- Calculates next_due_date (if vaccine_type is selected)
- Creates a VaccinationSchedule record
- Sets status to Pending/Due/Overdue based on calculated date

### Recording Follow-Ups

**When creating a medical record:**

1. Set "Follow-up Date" field
2. Enter "Follow-up Reason" (e.g., "Monitor wound healing")
3. Save medical record

**Result**: System automatically:
- Creates a FollowUpReminder
- Sets status based on date (Pending/Due/Overdue)

### Viewing Reminders

**For Pet Owners:**
- Dashboard shows upcoming vaccinations and follow-ups (limited display)
- Click "View All Reminders" to see comprehensive reminder page
- Color-coded by urgency (red = overdue, yellow = due soon, blue = upcoming)

**For Staff/Managers:**
- Reminders page shows all clinic's reminders
- Tables organized by urgency for quick prioritization
- Action buttons to contact owners or mark as sent

**URL**: `/reminders/`

### Updating Reminder Statuses

The system includes two automated management commands:

```bash
# Update vaccination schedule statuses based on current date
python manage.py update_vaccination_schedules

# Update follow-up reminder statuses based on current date
python manage.py update_followup_reminders
```

**Recommended Setup**:
Schedule these to run daily via cron or task scheduler:
```bash
# Linux crontab (run daily at 3 AM)
0 3 * * * cd /path/to/pawmily && python manage.py update_vaccination_schedules
0 3 * * * cd /path/to/pawmily && python manage.py update_followup_reminders
```

### Admin Actions

**Vaccination Schedule Admin**:
- Mark as Completed
- Mark as Skipped
- Manually Mark as Overdue
- Send Reminders (updates reminder_sent flag)

**Follow-Up Reminder Admin**:
- Mark as Completed
- Mark as Cancelled
- Send Reminders

## API / Integration Points

### Getting Reminders for a Pet
```python
from records.models import VaccinationSchedule, FollowUpReminder

pet = Pet.objects.get(id=1)

# Get all active vaccination schedules
vaccinations = pet.vaccination_schedules.filter(
    status__in=['pending', 'due', 'overdue']
)

# Get all active follow-up reminders
followups = pet.followup_reminders.filter(
    status__in=['pending', 'due', 'overdue']
)
```

### Checking if Vaccine is Overdue
```python
schedule = VaccinationSchedule.objects.get(id=1)
if schedule.is_overdue():
    # Send notification to owner
    pass

# Or check days until due
days = schedule.days_until_due()  # Negative if overdue
```

### Creating Reminders Manually
```python
from records.models import FollowUpReminder
from django.utils import timezone

# Create a follow-up reminder
reminder = FollowUpReminder.objects.create(
    pet=pet,
    medical_record=medical_record,
    follow_up_date=timezone.now().date() + timedelta(days=14),
    reason="Post-surgery check-up",
    status=FollowUpReminder.STATUS_PENDING
)
```

## Configuration

### Reminder Time Windows (Configurable in Models)

**Vaccinations**: Due status triggers when within **14 days** of due date
**Follow-ups**: Due status triggers when within **7 days** of due date

To adjust, edit `records/models.py`:
- `VaccinationSchedule.save()`: Change `14` to desired days
- `FollowUpReminder._update_followup_reminder()`: Change `7` to desired days

### Default Vaccine Intervals (seed_vaccines.py)

Edit `records/management/commands/seed_vaccines.py` before running to customize intervals

## Email Notifications (Optional Enhancement)

To add email notifications when reminders are created or status changes:

1. Override the save() methods in VaccinationSchedule and FollowUpReminder
2. Send email to pet owner
3. Mark reminder_sent_date when email is sent

Example:
```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    if not self.reminder_sent and self.status == self.STATUS_DUE:
        send_owner_email(self.pet.owner, self)
        self.reminder_sent = True
        self.reminder_sent_date = timezone.now()
        self.save(update_fields=['reminder_sent', 'reminder_sent_date'])
```

## Troubleshooting

**Problem**: Vaccinations not showing in schedules
- **Solution**: Ensure vaccine_type is set OR next_due_date is manually entered

**Problem**: Reminders status not updating
- **Solution**: Run management commands: `python manage.py update_vaccination_schedules`

**Problem**: Old reminders still showing
- **Solution**: Mark them as Completed/Cancelled in admin or check filter conditions in views

## Future Enhancements

1. **Email/SMS Notifications**: Auto-send reminders to pet owners
2. **Bulk Appointment Scheduling**: Create appointments for all due vaccinations
3. **Vaccination Certificate Export**: Generate PDF certificates
4. **Webhook Integration**: Send reminders to external reminder services
5. **ML Prediction**: Predict no-shows based on historical data
6. **Calendar View**: Visual calendar of upcoming vaccinations/follow-ups
7. **Multi-vet Coordination**: Track vaccinations across multiple clinics

---

**For Questions or Issues**: Contact the development team or check inline code documentation.
