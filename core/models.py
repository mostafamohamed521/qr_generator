from django.db import models


class ContactMessage(models.Model):
    email      = models.EmailField()
    message    = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} @ {self.created_at:%Y-%m-%d %H:%M}"
