from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    # Pages
    path('',                            views.teams_page,    name='teams'),
    path('<slug:slug>/',                views.team_detail,   name='detail'),
    path('accept/<str:token>/',         views.accept_invite, name='accept_invite'),

    # API
    path('api/my/',                     views.my_teams,      name='my_teams'),
    path('api/create/',                 views.create_team,   name='create'),
    path('api/<int:pk>/switch/',        views.switch_team,   name='switch'),
    path('api/<int:pk>/leave/',         views.leave_team,    name='leave'),
    path('api/<int:pk>/delete/',        views.delete_team,   name='delete'),
    path('api/<int:pk>/members/',       views.team_members,  name='members'),
    path('api/<int:pk>/invite/',        views.invite_member, name='invite'),
    path('api/<int:pk>/role/<int:user_id>/', views.change_role,  name='change_role'),
    path('api/<int:pk>/remove/<int:user_id>/', views.remove_member, name='remove'),
    path('api/<int:pk>/audit/',         views.audit_log,     name='audit_log'),
]
