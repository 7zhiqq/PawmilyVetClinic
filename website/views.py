from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return render(request, "landing.html")


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import DateTimeField, F, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from pawmily.pagination import paginate_queryset

from accounts.forms import PetForm, ProfileForm
from accounts.models import Pet, Profile, WalkInRegistration
from appointments.forms import AppointmentBookingForm, AppointmentStaffForm
from appointments.models import Appointment
from records.models import VaccinationSchedule, FollowUpReminder, VaccinationRecord, MedicalRecord
from billing.models import BillingRecord, Payment

User = get_user_model()


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return render(request, "landing.html")


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    role = getattr(profile, "role", None)

    context = {"role": role}

    if role == Profile.ROLE_PET_OWNER:
        context["pets"] = Pet.objects.filter(owner=request.user).order_by("name")
        context["book_form"] = AppointmentBookingForm(owner=request.user)
        context["book_error"] = None
        context["pet_form"]  = PetForm()
        context["profile_form"] = ProfileForm(instance=profile)

        # Upcoming appointments for the Reminders card
        context["upcoming_appointments"] = (
            Appointment.objects.select_related("pet")
            .filter(
                owner=request.user,
                appointment_date__gte=date.today(),
                status__in=[
                    Appointment.STATUS_PENDING,
                    Appointment.STATUS_CONFIRMED,
                ],
            )
            .order_by("appointment_date", "start_time")[:5]
        )

        # Upcoming vaccinations and follow-ups for all user's pets
        # Use date-based filtering to avoid stale stored statuses.
        user_pets = Pet.objects.filter(owner=request.user)
        context["upcoming_vaccinations"] = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")[:5]

        context["upcoming_followups"] = FollowUpReminder.objects.filter(
            pet__in=user_pets,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")[:5]

        # Recent billing records for the owner
        context["recent_billing"] = BillingRecord.objects.select_related(
            "appointment", "pet"
        ).filter(
            owner=request.user
        ).order_by("-created_at")[:5]

        # Queue View: owner's position in today's queue
        today = date.today()
        confirmed_today = list(
            Appointment.objects.select_related("pet")
            .filter(
                appointment_date=today,
                status=Appointment.STATUS_CONFIRMED,
            )
            .order_by("start_time", "slot_number")
        )
        served_count = Appointment.objects.filter(
            appointment_date=today,
            status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_NO_SHOW],
        ).count()

        my_queue_items = []
        now_serving_number = (served_count + 1) if confirmed_today else None
        for idx, apt in enumerate(confirmed_today):
            queue_number = served_count + idx + 1
            if apt.owner_id == request.user.id:
                my_queue_items.append({
                    "pet_name": apt.pet.name if apt.pet else "Walk-in",
                    "species": apt.pet.species if apt.pet else "other",
                    "queue_number": queue_number,
                    "position": idx + 1,
                    "ahead": idx,
                    "is_now_serving": idx == 0,
                    "reason": apt.reason or "",
                    "start_time": apt.start_time,
                })
        context["my_queue_items"] = my_queue_items
        context["now_serving_number"] = now_serving_number

    elif role in (Profile.ROLE_STAFF, Profile.ROLE_MANAGER):
        from django.db.models import Count
        today = timezone.localdate()
        day_start = timezone.make_aware(datetime.combine(today, time.min))
        next_day_start = day_start + timedelta(days=1)

        context["owners"]     = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username")
        context["pets"]       = Pet.objects.select_related("owner").order_by("owner__username", "name")
        context["staff_form"] = AppointmentStaffForm(initial={"appointment_type": Appointment.TYPE_WALK_IN})

        # Today's stats for the aside panel (staff): total excludes cancelled/rejected
        # to be consistent with today_appointments_count
        context["today_stats"] = Appointment.objects.filter(appointment_date=today).aggregate(
            total=Count("id", filter=~Q(status__in=[
                Appointment.STATUS_CANCELLED,
                Appointment.STATUS_REJECTED,
            ])),
            pending=Count("id", filter=Q(status=Appointment.STATUS_PENDING)),
            confirmed=Count("id", filter=Q(status=Appointment.STATUS_CONFIRMED)),
            completed=Count("id", filter=Q(status=Appointment.STATUS_COMPLETED)),
            no_show=Count("id", filter=Q(status=Appointment.STATUS_NO_SHOW)),
            cancelled=Count("id", filter=Q(status=Appointment.STATUS_CANCELLED)),
        )

        # Upcoming vaccinations and follow-ups for all pets (staff/manager view)
        # Upcoming vaccinations and follow-ups for all pets (staff/manager view)
        # Use date-based filtering so results are always current regardless of
        # when the update_vaccination_schedules management command last ran.
        _vax_soon_cutoff = today + timedelta(days=14)
        context["upcoming_vaccinations"] = VaccinationSchedule.objects.filter(
            next_due_date__lte=_vax_soon_cutoff,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")[:10]

        context["upcoming_followups"] = FollowUpReminder.objects.filter(
            follow_up_date__lte=today,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")[:10]

        # Main operational summary cards
        today_appointments_qs = Appointment.objects.filter(
            appointment_date=today,
        ).exclude(
            status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_REJECTED],
        )
        completed_today_appointments_qs = today_appointments_qs.filter(
            status=Appointment.STATUS_COMPLETED,
        )

        context["today_appointments_count"] = today_appointments_qs.count()
        context["today_appointments_list"] = (
            today_appointments_qs.select_related("pet", "owner")
            .order_by("start_time", "slot_number")[:8]
        )
        context["patients_served_today"] = completed_today_appointments_qs.count()
        context["vaccinations_administered_today"] = VaccinationRecord.objects.filter(
            date_administered=today,
        ).count()

        completed_billing_qs = BillingRecord.objects.filter(
            appointment__status=Appointment.STATUS_COMPLETED,
        )
        paid_completed_billing_qs = completed_billing_qs.filter(
            payment_status=BillingRecord.PAYMENT_STATUS_PAID,
        ).annotate(
            # Use actual payment timestamp when available; fall back to billing update time.
            paid_at=Coalesce(
                Max("payments__recorded_at"),
                F("updated_at"),
                output_field=DateTimeField(),
            )
        )
        pending_completed_billing_qs = completed_billing_qs.filter(
            total_amount__gt=F("amount_paid"),
        )

        context["total_revenue"] = paid_completed_billing_qs.aggregate(
            total=Sum("total_amount"),
        )["total"] or Decimal("0.00")

        today_revenue = paid_completed_billing_qs.filter(
            paid_at__gte=day_start,
            paid_at__lt=next_day_start,
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        context["today_revenue"] = today_revenue

        # Queue snapshot for "Now Serving / Waiting / Next"
        queue_items = list(
            Appointment.objects.select_related("pet", "owner")
            .filter(
                appointment_date=today,
                status=Appointment.STATUS_CONFIRMED,
            )
            .order_by("start_time", "slot_number")
        )
        served_count = Appointment.objects.filter(
            appointment_date=today,
            status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_NO_SHOW],
        ).count()

        now_serving = None
        next_in_line = None
        if queue_items:
            now_serving_appt = queue_items[0]
            now_serving = {
                "queue_number": served_count + 1,
                "pet_name": now_serving_appt.pet.name if now_serving_appt.pet else "Walk-in",
                "owner_name": now_serving_appt.owner.get_full_name() or now_serving_appt.owner.username,
                "reason": now_serving_appt.reason,
            }
            if len(queue_items) > 1:
                next_appt = queue_items[1]
                next_in_line = {
                    "queue_number": served_count + 2,
                    "pet_name": next_appt.pet.name if next_appt.pet else "Walk-in",
                    "owner_name": next_appt.owner.get_full_name() or next_appt.owner.username,
                    "reason": next_appt.reason,
                }

        context["queue_now_serving"] = now_serving
        context["queue_waiting_count"] = max(len(queue_items) - 1, 0)
        context["queue_next_in_line"] = next_in_line

        # Upcoming appointment table
        context["staff_upcoming_appointments"] = (
            Appointment.objects.select_related("pet", "owner")
            .filter(
                appointment_date__gte=today,
                status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED],
            )
            .order_by("appointment_date", "start_time", "slot_number")[:12]
        )

        now_time = timezone.localtime().time()
        tomorrow = today + timedelta(days=1)
        context["upcoming_next_appointments"] = (
            Appointment.objects.select_related("pet", "owner")
            .filter(
                status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED],
            )
            .filter(
                Q(appointment_date=today, start_time__gte=now_time)
                | Q(appointment_date=tomorrow)
            )
            .order_by("appointment_date", "start_time", "slot_number")[:8]
        )

        # Vaccination alerts (due soon + overdue)
        # Vaccination alerts (due soon + overdue) — filter by date directly so
        # stale stored statuses never cause alerts to be missed.
        soon_cutoff = today + timedelta(days=14)
        context["vaccination_alerts"] = (
            VaccinationSchedule.objects.select_related("pet", "vaccine_type")
            .filter(next_due_date__lte=soon_cutoff)
            .exclude(
                status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
            )
            .order_by("next_due_date")[:10]
        )

        # Billing overview
        context["pending_payments"] = pending_completed_billing_qs.count()
        context["paid_invoices_today"] = paid_completed_billing_qs.filter(
            paid_at__gte=day_start,
            paid_at__lt=next_day_start,
        ).count()

        # Revenue trend chart data (last 7 days) from fully paid invoices only.
        start_day = today - timedelta(days=6)
        start_day_start = timezone.make_aware(datetime.combine(start_day, time.min))
        grouped_revenue = {}
        # Iterate directly (not .values()) to preserve the per-billing-record GROUP BY
        # from the annotated paid_at, avoiding incorrect data merging.
        paid_revenue_rows = paid_completed_billing_qs.filter(
            paid_at__gte=start_day_start,
            paid_at__lt=next_day_start,
        )

        for row in paid_revenue_rows:
            local_day = timezone.localtime(row.paid_at).date()
            grouped_revenue[local_day] = (
                grouped_revenue.get(local_day, Decimal("0.00")) + row.total_amount
            )

        chart_points = []
        chart_labels = []
        chart_values = []
        for idx in range(7):
            day = start_day + timedelta(days=idx)
            amount = grouped_revenue.get(day) or Decimal("0.00")
            chart_labels.append(day.strftime("%a"))
            chart_values.append(float(amount))
            chart_points.append({
                "label": day.strftime("%a"),
                "amount": amount,
            })

        max_amount = max((point["amount"] for point in chart_points), default=Decimal("0.00"))
        max_amount = max_amount if max_amount > 0 else Decimal("1.00")
        for point in chart_points:
            point["height_pct"] = int((point["amount"] / max_amount) * 100)

        context["revenue_chart_data"] = {
            "labels": chart_labels,
            "values": chart_values,
        }
        context["revenue_chart_points"] = chart_points

        # Recent activity stream
        recent_activity = []

        for walkin in WalkInRegistration.objects.select_related("user", "created_by").order_by("-created_at")[:6]:
            recent_activity.append({
                "icon": "fa-user-plus",
                "title": "New walk-in registration",
                "description": walkin.user.get_full_name() or walkin.user.username,
                "timestamp": walkin.created_at,
            })

        for completed in Appointment.objects.select_related("pet", "owner").filter(
            status=Appointment.STATUS_COMPLETED,
        ).order_by("-updated_at")[:6]:
            recent_activity.append({
                "icon": "fa-calendar-check",
                "title": "Completed appointment",
                "description": completed.pet.name if completed.pet else (completed.owner.get_full_name() or completed.owner.username),
                "timestamp": completed.updated_at,
            })

        for record in MedicalRecord.objects.select_related("pet").order_by("-created_at")[:6]:
            recent_activity.append({
                "icon": "fa-notes-medical",
                "title": "Added medical record",
                "description": record.pet.name,
                "timestamp": record.created_at,
            })

        for payment in Payment.objects.select_related("billing_record").order_by("-recorded_at")[:6]:
            recent_activity.append({
                "icon": "fa-receipt",
                "title": "Recorded payment",
                "description": f"{payment.billing_record.invoice_number} - PHP {payment.amount}",
                "timestamp": payment.recorded_at,
            })

        context["recent_activity"] = sorted(
            recent_activity,
            key=lambda item: item["timestamp"],
            reverse=True,
        )[:10]

        if role == Profile.ROLE_MANAGER:
            # All-time clinic stats for manager panel
            context["clinic_stats"] = {
                "appointments": Appointment.objects.count(),
                "completed": Appointment.objects.filter(status=Appointment.STATUS_COMPLETED).count(),
                "pet_owners": User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).count(),
                "staff_active": User.objects.filter(
                    profile__role__in=[Profile.ROLE_STAFF, Profile.ROLE_MANAGER],
                    is_active=True,
                ).count(),
            }

            # Walk-in vs Scheduled appointment statistics
            # Only count completed appointments for meaningful type distribution
            completed_appointments_qs = Appointment.objects.filter(
                status=Appointment.STATUS_COMPLETED
            )
            total_completed_appointments = completed_appointments_qs.count()
            walk_in_count = completed_appointments_qs.filter(
                appointment_type=Appointment.TYPE_WALK_IN
            ).count()
            scheduled_count = completed_appointments_qs.filter(
                appointment_type=Appointment.TYPE_SCHEDULED
            ).count()

            context["walk_in_count"] = walk_in_count
            context["scheduled_count"] = scheduled_count
            if total_completed_appointments > 0:
                walk_in_pct = round((walk_in_count / total_completed_appointments) * 100)
                context["walk_in_percentage"] = walk_in_pct
                context["scheduled_percentage"] = 100 - walk_in_pct
            else:
                context["walk_in_percentage"] = 0
                context["scheduled_percentage"] = 0

            # Weekly revenue (last 7 days total)
            start_week = today - timedelta(days=6)
            start_week_start = timezone.make_aware(datetime.combine(start_week, time.min))
            weekly_revenue = paid_completed_billing_qs.filter(
                paid_at__gte=start_week_start,
                paid_at__lt=next_day_start,
            ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
            context["weekly_revenue"] = weekly_revenue

            # Monthly revenue trend (last 30 days)
            start_month = today - timedelta(days=29)
            start_month_start = timezone.make_aware(datetime.combine(start_month, time.min))
            monthly_revenue = paid_completed_billing_qs.filter(
                paid_at__gte=start_month_start,
                paid_at__lt=next_day_start,
            ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
            context["monthly_revenue"] = monthly_revenue

            # Clinic throughput metrics – count all active (non-cancelled/rejected) appointments
            active_last_7_days = Appointment.objects.filter(
                appointment_date__gte=start_week,
                appointment_date__lte=today,
            ).exclude(
                status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_REJECTED]
            ).count()
            context["avg_appointments_per_day"] = round(active_last_7_days / 7, 1)

            # Completion rate (percentage of appointments that were completed vs cancelled/rejected)
            total_concluded = Appointment.objects.filter(
                status__in=[
                    Appointment.STATUS_COMPLETED,
                    Appointment.STATUS_CANCELLED,
                    Appointment.STATUS_REJECTED,
                    Appointment.STATUS_NO_SHOW,
                ]
            ).count()
            completed_total = Appointment.objects.filter(
                status=Appointment.STATUS_COMPLETED
            ).count()
            context["completion_rate"] = (
                int((completed_total / total_concluded) * 100)
                if total_concluded > 0 else 0
            )

            # Total patients served (all time)
            context["total_patients_served"] = Appointment.objects.filter(
                status=Appointment.STATUS_COMPLETED
            ).count()

            # Total vaccinations administered (all time)
            context["total_vaccinations"] = VaccinationRecord.objects.count()

    return render(request, "dashboard.html", context)


@login_required
def reminders_view(request):
    """Display all vaccination and follow-up reminders for the user."""
    profile = getattr(request.user, "profile", None)
    role = getattr(profile, "role", None)
    
    context = {"role": role, "today": date.today()}
    today = date.today()

    if role == Profile.ROLE_PET_OWNER:
        # Show reminders for all user's pets — use date-based categorisation
        # so sections are always accurate regardless of stored status.
        user_pets = Pet.objects.filter(owner=request.user)
        _vax_due_cutoff = today + timedelta(days=14)
        _followup_due_cutoff = today + timedelta(days=7)

        vaccinations_overdue = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            next_due_date__lte=today,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")

        vaccinations_due = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            next_due_date__gt=today,
            next_due_date__lte=_vax_due_cutoff,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")

        vaccinations_pending = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            next_due_date__gt=_vax_due_cutoff,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")

        followups_overdue = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            follow_up_date__lte=today,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")

        followups_due = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            follow_up_date__gt=today,
            follow_up_date__lte=_followup_due_cutoff,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")

        followups_pending = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            follow_up_date__gt=_followup_due_cutoff,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")

        context["vaccinations_overdue"], context["vaccinations_overdue_pagination_query"] = paginate_queryset(
            request, vaccinations_overdue, per_page=10, page_param="vax_overdue_page"
        )
        context["vaccinations_due"], context["vaccinations_due_pagination_query"] = paginate_queryset(
            request, vaccinations_due, per_page=10, page_param="vax_due_page"
        )
        context["vaccinations_pending"], context["vaccinations_pending_pagination_query"] = paginate_queryset(
            request, vaccinations_pending, per_page=10, page_param="vax_pending_page"
        )
        context["followups_overdue"], context["followups_overdue_pagination_query"] = paginate_queryset(
            request, followups_overdue, per_page=10, page_param="followup_overdue_page"
        )
        context["followups_due"], context["followups_due_pagination_query"] = paginate_queryset(
            request, followups_due, per_page=10, page_param="followup_due_page"
        )
        context["followups_pending"], context["followups_pending_pagination_query"] = paginate_queryset(
            request, followups_pending, per_page=10, page_param="followup_pending_page"
        )
        
    elif role in (Profile.ROLE_STAFF, Profile.ROLE_MANAGER):
        # Show all overdue and due reminders across all pets — date-based for accuracy.
        _vax_due_cutoff = today + timedelta(days=14)
        _followup_due_cutoff = today + timedelta(days=7)

        vaccinations_overdue = VaccinationSchedule.objects.filter(
            next_due_date__lte=today,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")

        vaccinations_due = VaccinationSchedule.objects.filter(
            next_due_date__gt=today,
            next_due_date__lte=_vax_due_cutoff,
        ).exclude(
            status__in=[VaccinationSchedule.STATUS_COMPLETED, VaccinationSchedule.STATUS_SKIPPED]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")

        followups_overdue = FollowUpReminder.objects.filter(
            follow_up_date__lte=today,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")

        followups_due = FollowUpReminder.objects.filter(
            follow_up_date__gt=today,
            follow_up_date__lte=_followup_due_cutoff,
        ).exclude(
            status__in=[FollowUpReminder.STATUS_COMPLETED, FollowUpReminder.STATUS_CANCELLED]
        ).select_related("pet", "medical_record").order_by("follow_up_date")

        context["vaccinations_overdue"], context["vaccinations_overdue_pagination_query"] = paginate_queryset(
            request, vaccinations_overdue, per_page=10, page_param="vax_overdue_page"
        )
        context["vaccinations_due"], context["vaccinations_due_pagination_query"] = paginate_queryset(
            request, vaccinations_due, per_page=10, page_param="vax_due_page"
        )
        context["followups_overdue"], context["followups_overdue_pagination_query"] = paginate_queryset(
            request, followups_overdue, per_page=10, page_param="followup_overdue_page"
        )
        context["followups_due"], context["followups_due_pagination_query"] = paginate_queryset(
            request, followups_due, per_page=10, page_param="followup_due_page"
        )
    
    return render(request, "reminders.html", context)




