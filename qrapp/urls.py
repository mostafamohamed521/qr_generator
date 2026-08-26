from django.urls import path
from . import views

app_name = 'qrapp'

urlpatterns = [
    # Pages
    path('',                        views.index,         name='index'),
    path('analytics/',              views.analytics,     name='analytics'),
    path('dynamic/',               views.dynamic,       name='dynamic'),
    path('bulk/',                   views.bulk,          name='bulk'),
    path('scanner/',                views.scanner,       name='scanner'),

    # API
    path('api/generate/',           views.generate,      name='generate'),
    path('api/history/',            views.history,       name='history'),
    path('api/delete/<int:pk>/',    views.delete,        name='delete'),
    path('api/favorite/<int:pk>/',  views.toggle_favorite, name='toggle_favorite'),
    path('api/duplicate/<int:pk>/', views.duplicate,     name='duplicate'),
    path('api/clear/',              views.clear,         name='clear'),
    path('api/analytics/',          views.analytics_data,name='analytics_data'),
    path('api/bulk/',               views.bulk_generate, name='bulk_generate'),
    path('api/export-svg/<int:pk>/',views.export_svg,    name='export_svg'),
    path('api/export-csv/',        views.export_csv,    name='export_csv'),
    # Dynamic QR (Sprint 4)
    path('api/dynamic/',           views.dynamic_list,  name='dynamic_list'),
    path('api/dynamic/create/',    views.dynamic_create,name='dynamic_create'),
    path('api/dynamic/<int:pk>/update/', views.dynamic_update, name='dynamic_update'),
    path('api/dynamic/<int:pk>/delete/', views.dynamic_delete, name='dynamic_delete'),
    path('api/dynamic/<int:pk>/stats/',  views.dynamic_stats,  name='dynamic_stats'),
    path('api/save-scan/',             views.save_scan,      name='save_scan'),
]
