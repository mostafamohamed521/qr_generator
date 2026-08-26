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
    url = forms.URLField(max_length=2000, widget=forms.URLInput(attrs={**_I, 'placeholder': 'https://example.com'}))


class TextForm(forms.Form):
    # QR codes have a hard data ceiling (a few KB even at the largest
    # version/lowest error-correction). Without a cap here, a large paste
    # reaches qrcode's encoder and raises an unhandled DataOverflowError —
    # a 500 for the user and a wasted CPU-heavy encode for us. 2000 chars
    # comfortably fits at the size/error-correction this app uses.
    text = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={**_TA, 'rows': 4, 'placeholder': 'Enter any text…'}))


class ContactForm(forms.Form):
    first_name   = forms.CharField(max_length=60,  required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'First name'}))
    last_name    = forms.CharField(max_length=60,  required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Last name'}))
    phone        = forms.CharField(max_length=30,  required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Work phone'}))
    mobile       = forms.CharField(max_length=30,  required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Mobile'}))
    email        = forms.EmailField(max_length=254, required=False, widget=forms.EmailInput(attrs={**_I, 'placeholder': 'Email'}))
    organization = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Company'}))
    title        = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Job title'}))
    address      = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={**_TA, 'rows': 2, 'placeholder': 'Address'}))
    website      = forms.URLField(max_length=300,  required=False, widget=forms.URLInput(attrs={**_I, 'placeholder': 'https://'}))


class WiFiForm(forms.Form):
    # SSID/PSK caps match the real Wi-Fi spec (32-byte SSID, 8–63 char WPA
    # passphrase) — anything longer isn't a real network anyway.
    ssid       = forms.CharField(max_length=32, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Network name (SSID)'}))
    password   = forms.CharField(max_length=63, required=False, widget=forms.PasswordInput(attrs={**_I, 'placeholder': 'Password'}))
    encryption = forms.ChoiceField(
        choices=[('WPA', 'WPA / WPA2'), ('WEP', 'WEP'), ('nopass', 'Open (no password)')],
        widget=forms.Select(attrs=_SL),
    )


class SMSForm(forms.Form):
    phone   = forms.CharField(max_length=30,  widget=forms.TextInput(attrs={**_I, 'placeholder': '+1 555 000 0000'}))
    message = forms.CharField(max_length=500, widget=forms.Textarea(attrs={**_TA, 'rows': 3, 'placeholder': 'Your message…'}))


class EmailForm(forms.Form):
    email   = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={**_I, 'placeholder': 'recipient@example.com'}))
    subject = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={**_I, 'placeholder': 'Subject'}))
    body    = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={**_TA, 'rows': 3, 'placeholder': 'Body…'}))


class PhoneForm(forms.Form):
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={**_I, 'placeholder': '+1 555 000 0000'}))


class LocationForm(forms.Form):
    latitude  = forms.FloatField(widget=forms.NumberInput(attrs={**_I, 'placeholder': '40.7128',  'step': 'any'}))
    longitude = forms.FloatField(widget=forms.NumberInput(attrs={**_I, 'placeholder': '-74.0060', 'step': 'any'}))

    def clean_latitude(self):
        v = self.cleaned_data['latitude']
        if not (-90 <= v <= 90):
            raise forms.ValidationError('Latitude must be between -90 and 90.')
        return v

    def clean_longitude(self):
        v = self.cleaned_data['longitude']
        if not (-180 <= v <= 180):
            raise forms.ValidationError('Longitude must be between -180 and 180.')
        return v
