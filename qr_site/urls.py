from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

# Custom error handlers
handler404 = 'qr_site.views.handler404'
handler500 = 'qr_site.views.handler500'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Service Worker at root scope so it can intercept all pages
from django.views.static import serve as static_serve
from pathlib import Path as _Path

_static_root = _Path(__file__).resolve().parent.parent / 'static'
urlpatterns += [
    path('sw.js', static_serve, {
        'path': 'sw.js', 'document_root': _static_root,
    }, name='sw'),
    path('manifest.json', static_serve, {
        'path': 'manifest.json', 'document_root': _static_root,
    }, name='manifest'),
]

# Everything below is language-prefixed (/en/..., /ar/...) so the whole
# site — marketing pages AND the app — can be served in either language.
urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('app/', include('qrapp.urls')),
    path('teams/', include('teams.urls')),
    path('billing/', include('billing.urls')),
    path('api/v1/', include('api.urls')),
    path('dashboard/', include('dashboard.urls')),
    prefix_default_language=False,
)

# Dynamic QR redirect — language-prefix free so phone cameras work everywhere
from qrapp import views as qr_views
urlpatterns += [
    path('r/<str:short_code>/', qr_views.dynamic_redirect, name='dynamic_redirect'),
]
