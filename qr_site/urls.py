from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),  # language switcher endpoint
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Everything below is language-prefixed (/en/..., /ar/...) so the whole
# site — marketing pages AND the app — can be served in either language.
urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('app/', include('qrapp.urls')),
    path('teams/', include('teams.urls')),
    path('billing/', include('billing.urls')),
    path('api/v1/', include('api.urls')),
    prefix_default_language=False,
)

# Dynamic QR redirect — language-prefix free so phone cameras work everywhere
from qrapp import views as qr_views
urlpatterns += [
    path('r/<str:short_code>/', qr_views.dynamic_redirect, name='dynamic_redirect'),
]
