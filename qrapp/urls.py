from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generate/', views.generate_qr, name='generate_qr'),
    path('history/', views.get_history, name='history'),
    path('delete/<int:id>/', views.delete_history, name='delete_history'),
]