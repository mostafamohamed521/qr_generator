"""
forms.py
--------
One form per QR type.  All share the same CSS class helpers.
"""
from django import forms

_I  = {'class': 'fi'}          # form-input
_TA = {'class': 'ft'}          # form-textarea
_SL = {'class': 'fs'}          # form-select


class URLForm(forms.Form):
    url = forms.URLField(widget=forms.URLInput(attrs={**_I, 'placeholder': 'https://example.com'}))


class TextForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea(attrs={**_TA, 'rows': 4, 'placeholder': 'Enter any text…'}))


class ContactForm(forms.Form):
    first_name   = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'First name'}))
    last_name    = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Last name'}))
    phone        = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Work phone'}))
    mobile       = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Mobile'}))
    email        = forms.EmailField(required=False, widget=forms.EmailInput(attrs={**_I, 'placeholder': 'Email'}))
    organization = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Company'}))
    title        = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Job title'}))
    address      = forms.CharField(required=False, widget=forms.Textarea(attrs={**_TA, 'rows': 2, 'placeholder': 'Address'}))
    website      = forms.URLField(required=False, widget=forms.URLInput(attrs={**_I, 'placeholder': 'https://'}))


class WiFiForm(forms.Form):
    ssid       = forms.CharField(widget=forms.TextInput(attrs={**_I, 'placeholder': 'Network name (SSID)'}))
    password   = forms.CharField(required=False, widget=forms.PasswordInput(attrs={**_I, 'placeholder': 'Password'}))
    encryption = forms.ChoiceField(
        choices=[('WPA', 'WPA / WPA2'), ('WEP', 'WEP'), ('nopass', 'Open (no password)')],
        widget=forms.Select(attrs=_SL),
    )


class SMSForm(forms.Form):
    phone   = forms.CharField(widget=forms.TextInput(attrs={**_I, 'placeholder': '+1 555 000 0000'}))
    message = forms.CharField(widget=forms.Textarea(attrs={**_TA, 'rows': 3, 'placeholder': 'Your message…'}))


class EmailForm(forms.Form):
    email   = forms.EmailField(widget=forms.EmailInput(attrs={**_I, 'placeholder': 'recipient@example.com'}))
    subject = forms.CharField(required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Subject'}))
    body    = forms.CharField(required=False, widget=forms.Textarea(attrs={**_TA, 'rows': 3, 'placeholder': 'Body…'}))


class PhoneForm(forms.Form):
    phone = forms.CharField(widget=forms.TextInput(attrs={**_I, 'placeholder': '+1 555 000 0000'}))


class LocationForm(forms.Form):
    latitude  = forms.FloatField(widget=forms.NumberInput(attrs={**_I, 'placeholder': '40.7128',  'step': 'any'}))
    longitude = forms.FloatField(widget=forms.NumberInput(attrs={**_I, 'placeholder': '-74.0060', 'step': 'any'}))
