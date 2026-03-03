"""
Role-based access control middleware for Pawmily Veterinary Clinic.
"""
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from .models import Profile


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce role-based access control.
    
    Routes are protected based on user roles:
    - Client (Pet Owner) routes: /pets/, /profile/, /appointments/book/, /appointments/calendar/
    - Staff routes: /appointments/queue/, /appointments/manage/, /appointments/schedule/
    - Manager routes: /invitations/
    """
    
    # Define role-based route patterns
    CLIENT_ROUTES = [
        '/pets/',
        '/profile/',
        '/appointments/book/',
        '/appointments/calendar/',
    ]
    
    STAFF_ROUTES = [
        '/appointments/queue/',
        '/appointments/manage/',
        '/appointments/schedule/',
        '/appointments/calendar/',
    ]
    
    MANAGER_ROUTES = [
        '/invitations/',
    ]
    
    # Public routes that don't require authentication
    PUBLIC_ROUTES = [
        '/login/',
        '/logout/',
        '/register/',
        '/invite/',
        '/',
        '/admin/',
        '/static/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip middleware for public routes
        if any(request.path.startswith(route) for route in self.PUBLIC_ROUTES):
            return self.get_response(request)
        
        # Check if user is authenticated for protected routes
        if not request.user.is_authenticated:
            return redirect(reverse('login'))
        
        # Check if account is active
        if not request.user.is_active:
            from django.contrib.auth import logout
            logout(request)
            return redirect(reverse('login') + '?inactive=1')
        
        # Get user role
        try:
            profile = request.user.profile
            user_role = profile.role
        except Profile.DoesNotExist:
            # If no profile exists, allow superusers
            if request.user.is_superuser:
                return self.get_response(request)
            return HttpResponseForbidden(
                "Your account doesn't have a valid profile. Please contact the administrator."
            )
        
        # Check role-based access
        path = request.path
        
        # Manager has access to everything
        if user_role == Profile.ROLE_MANAGER:
            return self.get_response(request)
        
        # Staff has access to staff and some client routes
        if user_role == Profile.ROLE_STAFF:
            # Check if trying to access manager-only routes
            if any(path.startswith(route) for route in self.MANAGER_ROUTES):
                return HttpResponseForbidden(
                    "You don't have permission to access this page. Manager access required."
                )
            # Allow staff routes and calendar
            return self.get_response(request)
        
        # Client (Pet Owner) has access to client routes only
        if user_role == Profile.ROLE_PET_OWNER:
            # Check if trying to access staff or manager routes
            staff_only_routes = [
                '/appointments/manage/',
                '/appointments/schedule/',
            ]
            if any(path.startswith(route) for route in staff_only_routes):
                return HttpResponseForbidden(
                    "You don't have permission to access this page. Staff access required."
                )
            if any(path.startswith(route) for route in self.MANAGER_ROUTES):
                return HttpResponseForbidden(
                    "You don't have permission to access this page. Manager access required."
                )
        
        return self.get_response(request)


def require_role(*allowed_roles):
    """
    Decorator to restrict view access to specific roles.
    
    Usage:
        @require_role(Profile.ROLE_MANAGER)
        def my_view(request):
            ...
        
        @require_role(Profile.ROLE_STAFF, Profile.ROLE_MANAGER)
        def another_view(request):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(reverse('login'))
            
            if not request.user.is_active:
                from django.contrib.auth import logout
                logout(request)
                return redirect(reverse('login') + '?inactive=1')
            
            try:
                profile = request.user.profile
                user_role = profile.role
            except Profile.DoesNotExist:
                if request.user.is_superuser:
                    return view_func(request, *args, **kwargs)
                return HttpResponseForbidden(
                    "Your account doesn't have a valid profile."
                )
            
            if user_role not in allowed_roles:
                role_names = ', '.join([
                    dict(Profile.ROLE_CHOICES).get(role, role)
                    for role in allowed_roles
                ])
                return HttpResponseForbidden(
                    f"Access denied. This page requires: {role_names}"
                )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
