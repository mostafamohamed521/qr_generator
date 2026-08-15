import hashlib
from django.db import migrations, models


def backfill_key_hashes(apps, schema_editor):
    """
    Populate key_hash/key_prefix for every existing APIKey from its current
    plaintext `key` value. Purely additive — the plaintext column itself is
    left untouched here, so this is safe to run against a database that
    already has real keys in production; nothing about how those keys
    authenticate changes for their holders (they keep using the same raw
    key string they were given, the server now just compares its hash
    instead of the plaintext).
    """
    APIKey = apps.get_model('api', 'APIKey')
    for k in APIKey.objects.exclude(key__isnull=True).exclude(key=''):
        k.key_hash = hashlib.sha256(k.key.encode()).hexdigest()
        k.key_prefix = k.key[:14]
        k.save(update_fields=['key_hash', 'key_prefix'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        # Step 1: add the new columns without a uniqueness constraint yet —
        # every existing row starts with key_hash='', and a unique
        # constraint can't be added while more than one row shares that
        # default.
        migrations.AddField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(max_length=64, default='', db_index=True),
        ),
        migrations.AddField(
            model_name='apikey',
            name='key_prefix',
            field=models.CharField(max_length=16, blank=True, default=''),
        ),
        # Step 2: the plaintext column becomes optional — new keys
        # (created after this migration, see api/views.py create_key)
        # never populate it. Existing plaintext values are NOT touched.
        migrations.AlterField(
            model_name='apikey',
            name='key',
            field=models.CharField(max_length=120, unique=True, null=True, blank=True, default=None),
        ),
        # Step 3: backfill key_hash/key_prefix for every existing row from
        # its current plaintext value.
        migrations.RunPython(backfill_key_hashes, noop_reverse),
        # Step 4: now that every real row has a distinct, populated
        # key_hash, enforce uniqueness on it (this is what authentication
        # actually looks up by from here on).
        migrations.AlterField(
            model_name='apikey',
            name='key_hash',
            field=models.CharField(max_length=64, unique=True, db_index=True, default=''),
        ),
    ]
