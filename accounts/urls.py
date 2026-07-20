from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/remove-avatar/', views.remove_avatar_view, name='remove_avatar'),
    path('profile/delete/', views.delete_account_view, name='delete_account'),

    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password_view, name='reset_password'),

    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),

    path('2fa/setup/', views.twofa_setup_view, name='twofa_setup'),
    path('2fa/disable/', views.twofa_disable_view, name='twofa_disable'),
    path('2fa/verify/', views.twofa_verify_view, name='twofa_verify'),
]
