from django.db import models

class ChatLog(models.Model):
    session_key = models.CharField(max_length=100)
    user_role   = models.CharField(max_length=20, null=True, blank=True)
    user_id     = models.IntegerField(null=True, blank=True)
    user_message = models.TextField()
    bot_response = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Chat Log'
        ordering = ['-created_at']

    def __str__(self):
        return f"Chat [{self.session_key[:8]}] — {self.created_at:%d %b %Y}"
