from django.urls import path
from . import views

app_name = 'qrapp'

urlpatterns = [
    # Pages
    path('',                        views.index,         name='index'),
    path('analytics/',              views.analytics,     name='analytics'),
    path('bulk/',                   views.bulk,          name='bulk'),
    path('scanner/',                views.scanner,       name='scanner'),

    # API
    path('api/generate/',           views.generate,      name='generate'),
    path('api/history/',            views.history,       name='history'),
    path('api/delete/<int:pk>/',    views.delete,        name='delete'),
    path('api/clear/',              views.clear,         name='clear'),
    path('api/analytics/',          views.analytics_data,name='analytics_data'),
    path('api/bulk/',               views.bulk_generate, name='bulk_generate'),
    path('api/export-svg/<int:pk>/',views.export_svg,    name='export_svg'),
    path('api/export-csv/',        views.export_csv,    name='export_csv'),
]
