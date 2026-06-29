from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import RegisterForm, LoginForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('qrapp:index')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)
        messages.success(request, 'Welcome to QR Forge! Your account is ready.')
        return redirect('qrapp:index')

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('qrapp:index')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data['user']
        auth_login(request, user)
        if form.cleaned_data.get('remember'):
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
        else:
            request.session.set_expiry(0)  # browser-session only
        next_url = request.GET.get('next') or reverse('qrapp:index')
        return redirect(next_url)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    auth_logout(request)
    return redirect('core:landing')


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    return render(request, 'accounts/profile.html')
