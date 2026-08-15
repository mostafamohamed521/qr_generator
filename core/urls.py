from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('pricing/', views.pricing, name='pricing'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('contact/submit/', views.contact_submit, name='contact_submit'),
    path('faq/', views.faq, name='faq'),
    path('robots.txt', views.robots_txt, name='robots'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap'),
]
