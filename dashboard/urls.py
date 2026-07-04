from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',                      views.dashboard,      name='home'),
    path('users/',                views.users_page,     name='users'),
    path('api/stats/',            views.stats,          name='stats'),
    path('api/users/',            views.users_list,     name='users_list'),
    path('api/users/<int:pk>/toggle/',  views.toggle_user,  name='toggle_user'),
    path('api/users/<int:pk>/delete/',  views.delete_user,  name='delete_user'),
    path('api/export-users/',     views.export_users_csv, name='export_users'),
]
