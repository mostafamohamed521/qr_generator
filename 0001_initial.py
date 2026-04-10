from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='QRHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qr_type', models.CharField(choices=[
                    ('url', 'URL'), ('text', 'Text'), ('contact', 'Contact'),
                    ('wifi', 'WiFi'), ('sms', 'SMS'), ('email', 'Email'),
                    ('phone', 'Phone'), ('location', 'Location'),
                ], max_length=20)),
                ('content', models.TextField()),
                ('label', models.CharField(blank=True, default='', max_length=100)),
                ('qr_color', models.CharField(default='black', max_length=20)),
                ('bg_color', models.CharField(default='white', max_length=20)),
                ('qr_size', models.IntegerField(default=300)),
                ('qr_image', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
