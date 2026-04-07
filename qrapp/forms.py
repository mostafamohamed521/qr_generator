from django import forms

class URLForm(forms.Form):
    url = forms.URLField(label='URL', widget=forms.URLInput(attrs={
        'class': 'form-input',
        'placeholder': 'https://example.com'
    }))

class TextForm(forms.Form):
    text = forms.CharField(label='Text', widget=forms.Textarea(attrs={
        'class': 'form-textarea',
        'rows': 4,
        'placeholder': 'Enter your text here...'
    }))

class ContactForm(forms.Form):
    first_name = forms.CharField(label='First Name', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    last_name = forms.CharField(label='Last Name', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    phone = forms.CharField(label='Phone Number', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    mobile = forms.CharField(label='Mobile', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    email = forms.EmailField(label='Email', required=False, widget=forms.EmailInput(attrs={'class': 'form-input'}))
    organization = forms.CharField(label='Organization', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    title = forms.CharField(label='Job Title', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    address = forms.CharField(label='Address', required=False, widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}))
    website = forms.URLField(label='Website', required=False, widget=forms.URLInput(attrs={'class': 'form-input'}))

class WiFiForm(forms.Form):
    ssid = forms.CharField(label='Network Name (SSID)', widget=forms.TextInput(attrs={'class': 'form-input'}))
    password = forms.CharField(label='Password', required=False, widget=forms.PasswordInput(attrs={'class': 'form-input'}))
    encryption = forms.ChoiceField(label='Encryption Type', choices=[
        ('WPA', 'WPA/WPA2'),
        ('WEP', 'WEP'),
        ('nopass', 'No Password')
    ], widget=forms.Select(attrs={'class': 'form-select'}))

class SMSForm(forms.Form):
    phone = forms.CharField(label='Phone Number', widget=forms.TextInput(attrs={'class': 'form-input'}))
    message = forms.CharField(label='Message', widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}))

class EmailForm(forms.Form):
    email = forms.EmailField(label='Email Address', widget=forms.EmailInput(attrs={'class': 'form-input'}))
    subject = forms.CharField(label='Subject', required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    body = forms.CharField(label='Message Body', required=False, widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}))