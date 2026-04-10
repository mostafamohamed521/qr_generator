from django.urls import path
from . import views

app_name = 'qrapp'

urlpatterns = [
    path('',                   views.index,   name='index'),
    path('api/generate/',      views.generate, name='generate'),
    path('api/history/',       views.history,  name='history'),
    path('api/delete/<int:pk>/', views.delete, name='delete'),
    path('api/clear/',         views.clear,    name='clear'),
]
