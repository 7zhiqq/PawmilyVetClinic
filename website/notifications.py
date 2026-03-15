from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import OwnerNotification


def _clinic_name():
    return getattr(settings, "CLINIC_NAME", "PAWMILY Veterinary Clinic")


def _appointment_label(appointment):
    pet_name = appointment.pet.name if appointment.pet else "your pet"
    appt_date = appointment.appointment_date.strftime("%B %d")
    appt_time = appointment.start_time.strftime("%I:%M %p")
    return pet_name, appt_date, appt_time


def _send_owner_email(user, subject, message):
    if not user.email:
        return False

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return True


def create_owner_notification(
    *,
    user,
    notification_type,
    title,
    message,
    appointment=None,
    billing_record=None,
    payment=None,
    event_key=None,
    link_url="",
    send_email=False,
    email_subject=None,
    update_existing=False,
    is_important=True,
):
    defaults = {
        "user": user,
        "appointment": appointment,
        "billing_record": billing_record,
        "payment": payment,
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "link_url": link_url,
        "is_important": is_important,
    }

    if event_key:
        notification, created = OwnerNotification.objects.get_or_create(
            event_key=event_key,
            defaults=defaults,
        )
        if (not created) and update_existing:
            notification.title = title
            notification.message = message
            notification.link_url = link_url
            notification.notification_type = notification_type
            notification.appointment = appointment
            notification.billing_record = billing_record
            notification.payment = payment
            notification.user = user
            notification.is_important = is_important
            notification.save(
                update_fields=[
                    "title",
                    "message",
                    "link_url",
                    "notification_type",
                    "appointment",
                    "billing_record",
                    "payment",
                    "user",
                    "is_important",
                    "updated_at",
                ]
            )
    else:
        notification = OwnerNotification.objects.create(**defaults)
        created = True

    if send_email and (created or update_existing) and not notification.email_sent:
        sent = _send_owner_email(user, email_subject or title, message)
        if sent:
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=["email_sent", "email_sent_at", "updated_at"])

    return notification


def notify_appointment_requested(appointment):
    pet_name, appt_date, appt_time = _appointment_label(appointment)
    message = (
        f"Your appointment request for {pet_name} has been successfully submitted. "
        "Please wait for clinic confirmation.\n"
        f"Date: {appt_date}\n"
        f"Time: {appt_time}"
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_APPOINTMENT_REQUESTED,
        title="Appointment request submitted",
        message=message,
        event_key=f"appointment_requested:{appointment.id}",
        link_url=reverse("appointment_calendar"),
        send_email=True,
        email_subject="Appointment request submitted",
    )


def notify_appointment_confirmed(appointment):
    pet_name, appt_date, appt_time = _appointment_label(appointment)
    message = (
        f"Your appointment for {pet_name} on {appt_date} at {appt_time} has been confirmed."
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_APPOINTMENT_CONFIRMED,
        title="Appointment confirmed",
        message=message,
        event_key=f"appointment_confirmed:{appointment.id}:{appointment.updated_at.timestamp()}",
        link_url=reverse("appointment_calendar"),
        send_email=True,
        email_subject="Appointment confirmed",
    )


def notify_appointment_rejected(appointment):
    pet_name, _, _ = _appointment_label(appointment)
    message = (
        f"Unfortunately, your appointment request for {pet_name} could not be scheduled. "
        "Please select another available time."
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_APPOINTMENT_REJECTED,
        title="Appointment rejected",
        message=message,
        event_key=f"appointment_rejected:{appointment.id}:{appointment.updated_at.timestamp()}",
        link_url=reverse("appointment_calendar"),
        send_email=True,
        email_subject="Appointment request update",
    )


def notify_appointment_completed(appointment):
    pet_name, _, _ = _appointment_label(appointment)
    message = (
        f"Your appointment for {pet_name} has been completed. "
        "You can now review the medical records and billing details."
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_APPOINTMENT_COMPLETED,
        title="Appointment completed",
        message=message,
        event_key=f"appointment_completed:{appointment.id}:{appointment.updated_at.timestamp()}",
        link_url=reverse("billing_list"),
        send_email=True,
        email_subject="Appointment completed",
    )


def notify_appointment_no_show(appointment):
    pet_name, _, _ = _appointment_label(appointment)
    message = (
        f"Your appointment for {pet_name} has been marked as No Show because the scheduled time has passed."
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_APPOINTMENT_NO_SHOW,
        title="Appointment marked as no show",
        message=message,
        event_key=f"appointment_no_show:{appointment.id}:{appointment.updated_at.timestamp()}",
        link_url=reverse("appointment_calendar"),
        send_email=True,
        email_subject="Appointment no-show update",
    )


def notify_appointment_reminder_24h(appointment):
    pet_name, appt_date, appt_time = _appointment_label(appointment)
    clinic = _clinic_name()
    message = (
        f"Your pet {pet_name} has an upcoming appointment tomorrow at {clinic}.\n"
        f"Date: {appt_date}\n"
        f"Time: {appt_time}\n"
        f"Service/Reason: {appointment.reason or 'General consultation'}\n"
        "Please arrive on time for your scheduled visit."
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_APPOINTMENT_REMINDER_24H,
        title="Appointment reminder: tomorrow",
        message=message,
        event_key=f"appointment_reminder_24h:{appointment.id}:{appointment.appointment_date.isoformat()}",
        link_url=reverse("appointment_calendar"),
        send_email=True,
        email_subject="Appointment reminder for tomorrow",
    )


def notify_same_day_queue_update(appointment, *, queue_position, current_serving_number):
    pet_name, appt_date, appt_time = _appointment_label(appointment)
    message = (
        f"Your appointment for {pet_name} is scheduled for today at {appt_time}.\n"
        f"Date: {appt_date}\n"
        f"Your queue position: #{queue_position}\n"
        f"The clinic is currently serving Queue #{current_serving_number}.\n"
        "Please prepare to arrive at the clinic."
    )
    create_owner_notification(
        user=appointment.owner,
        appointment=appointment,
        notification_type=OwnerNotification.TYPE_QUEUE_TODAY,
        title="Today's appointment queue update",
        message=message,
        event_key=f"queue_today:{appointment.id}:{appointment.appointment_date.isoformat()}",
        link_url=reverse("appointment_queue") + f"?date={appointment.appointment_date.isoformat()}",
        send_email=False,
        update_existing=True,
    )


def notify_billing_generated(billing_record):
    pet_name = billing_record.pet.name if billing_record.pet else "your recent visit"
    message = (
        f"A billing statement has been generated for your recent visit with {pet_name}. "
        "Please review the billing details in your dashboard."
    )
    create_owner_notification(
        user=billing_record.owner,
        billing_record=billing_record,
        appointment=billing_record.appointment,
        notification_type=OwnerNotification.TYPE_BILLING_GENERATED,
        title="Billing statement generated",
        message=message,
        event_key=f"billing_generated:{billing_record.id}",
        link_url=reverse("billing_detail", args=[billing_record.id]),
        send_email=True,
        email_subject="Billing statement generated",
    )


def notify_payment_submitted(payment):
    billing_record = payment.billing_record
    pet_name = billing_record.pet.name if billing_record.pet else "your pet"
    message = (
        f"Your payment submission for {pet_name} has been received and is pending verification by clinic staff."
    )
    create_owner_notification(
        user=billing_record.owner,
        billing_record=billing_record,
        payment=payment,
        appointment=billing_record.appointment,
        notification_type=OwnerNotification.TYPE_PAYMENT_SUBMITTED,
        title="Payment submission received",
        message=message,
        event_key=f"payment_submitted:{payment.id}",
        link_url=reverse("billing_detail", args=[billing_record.id]),
        send_email=True,
        email_subject="Payment submission received",
    )


def notify_payment_approved(payment):
    billing_record = payment.billing_record
    pet_name = billing_record.pet.name if billing_record.pet else "your pet"
    message = (
        f"Your payment for {pet_name}'s visit has been successfully verified and marked as paid."
    )
    create_owner_notification(
        user=billing_record.owner,
        billing_record=billing_record,
        payment=payment,
        appointment=billing_record.appointment,
        notification_type=OwnerNotification.TYPE_PAYMENT_APPROVED,
        title="Payment approved",
        message=message,
        event_key=f"payment_approved:{payment.id}",
        link_url=reverse("billing_detail", args=[billing_record.id]),
        send_email=True,
        email_subject="Payment approved",
    )
