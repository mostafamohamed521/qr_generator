from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django import forms


class RegisterForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    password = forms.CharField(min_length=8)

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_password(self):
        pw = self.cleaned_data['password']
        try:
            validate_password(pw)
        except ValidationError as e:
            raise ValidationError(' '.join(e.messages))
        return pw

    def save(self):
        name = self.cleaned_data['name'].strip()
        email = self.cleaned_data['email']
        password = self.cleaned_data['password']
        first_name, _, last_name = name.partition(' ')
        user = User.objects.create_user(
            username=email, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )
        return user


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField()
    remember = forms.BooleanField(required=False)

    error_messages = {
        'invalid': 'Incorrect email or password.',
    }

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')
        if email and password:
            user = authenticate(username=email, password=password)
            if user is None:
                raise ValidationError(self.error_messages['invalid'])
            cleaned['user'] = user
        return cleaned
