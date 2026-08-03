from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Admin login required to access this page.")
            return redirect('login')
        if not request.user.is_admin():
            messages.error(request, "Access denied. You do not have Admin privileges.")
            if request.user.is_driver():
                return redirect('driver-portal')
            return redirect('user-dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def driver_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Driver login required to access the Driver Portal.")
            return redirect('login')
        if not request.user.is_driver():
            messages.error(request, "Access denied. Only Drivers can access the Driver Portal.")
            if request.user.is_admin():
                return redirect('admin-dashboard')
            return redirect('user-dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def user_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to access your User Dashboard.")
            return redirect('login')
        if not request.user.is_user():
            if request.user.is_admin():
                return redirect('admin-dashboard')
            elif request.user.is_driver():
                return redirect('driver-portal')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
