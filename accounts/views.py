"""
Sprint 0: routing placeholders only.
Sprint 1 implements real register/login/logout/password-reset/2FA/OAuth logic.
"""
from django.shortcuts import render


def login_view(request):
    return render(request, 'accounts/login.html')


def register_view(request):
    return render(request, 'accounts/register.html')


def logout_view(request):
    return render(request, 'accounts/login.html')


def profile_view(request):
    return render(request, 'accounts/profile.html')
