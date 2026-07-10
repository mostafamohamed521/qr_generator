from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Developer portal (session auth)
    path('docs/',                   views.docs,                name='docs'),
    path('keys/create/',            views.create_key,          name='create_key'),
    path('keys/<int:pk>/revoke/',   views.revoke_key,          name='revoke_key'),
    path('webhooks/create/',        views.create_webhook,      name='create_webhook'),
    path('webhooks/<int:pk>/delete/', views.delete_webhook,    name='delete_webhook'),

    # REST API (Bearer token)
    path('me/',                     views.api_me,              name='me'),
    path('generate/',               views.api_generate,        name='generate'),
    path('qrcodes/',                views.api_list,            name='list'),
    path('qrcodes/<int:pk>/',       views.api_get,             name='get'),
    path('qrcodes/<int:pk>/delete/',views.api_delete,          name='delete'),
    path('dynamic/',                views.api_dynamic_list,    name='dynamic_list'),
    path('dynamic/create/',         views.api_dynamic_create,  name='dynamic_create'),
    path('dynamic/<int:pk>/update/',views.api_dynamic_update,  name='dynamic_update'),
]
