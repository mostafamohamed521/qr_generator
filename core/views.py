from django.shortcuts import render


def landing(request):
    return render(request, 'core/landing.html')


def pricing(request):
    return render(request, 'core/pricing.html')


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    return render(request, 'core/contact.html')


def faq(request):
    return render(request, 'core/faq.html')
