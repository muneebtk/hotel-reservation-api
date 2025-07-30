import logging
from functools import wraps
from django.shortcuts import redirect, render
from django.contrib import messages
from user.models import User, VendorProfile
from django.db.models import Q

logger = logging.getLogger('lessons')

def vendor_required(view_func):
    """
    Custom decorator to check if the user is authenticated and has a VendorProfile.
    Redirects to login or an error page if the user is not a valid vendor.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            logger.info("Unauthenticated access attempt. Redirecting to login.")
            request.session.flush()
            messages.error(request, "You must be logged in to access this page.")
            return redirect('loginn')
        user = None
        try:
            # Check if the user has a VendorProfile
            user = User.objects.get(id=request.user.id, is_active = True)
            logger.info(f"vendor_required ------> user: {user}")
        except User.DoesNotExist:
            logger.error(f"No user found for user: {request.user.id} ({request.user.username})")
            messages.error(request, "You do not have a user account.")
            return redirect('loginn')
        try:
            vendor_profile = VendorProfile.objects.get(user=user)
            logger.info(f"vendor_required ------> vendor_profile: {vendor_profile}")
            if vendor_profile:
                logger.info(f"VendorProfile exists for user: {request.user.id} ({request.user.username})")
                return view_func(request, *args, **kwargs)
        except VendorProfile.DoesNotExist:
            logger.error(f"No VendorProfile found for user: {request.user.id} ({request.user.username})")
            messages.error(request, "You do not have a vendor account.")
            return redirect('loginn')

        messages.error(request, "Access denied.")
        return redirect('loginn')

    return _wrapped_view

def super_admin_required(view_func):
    """
    Custom decorator to check if the user is authenticated and has a SuperAdmin profile.
    Redirects to a 404 page if the user does not have a SuperAdmin profile.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            logger.error(f"Unauthenticated user {request.user.username} tried to access a restricted page.")
            return render(request, "superuser/404.html")

        user_profile = VendorProfile.objects.filter(user=request.user, category__in=['admin', 'superadmin'],user__is_active=True)

        if user_profile.exists():
            logger.info(f"Super admin {request.user.first_name} accessed the page.")
            return view_func(request, *args, **kwargs)
        else:
            logger.error(f"User {request.user.username} does not have a Super Admin or Admin profile.")
            return redirect('loginn')

    return _wrapped_view
