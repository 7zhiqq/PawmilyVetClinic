from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return render(request, "landing.html")


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    role = getattr(profile, "role", None)

    return render(
        request,
        "dashboard.html",
        {
            "role": role,
        },
    )