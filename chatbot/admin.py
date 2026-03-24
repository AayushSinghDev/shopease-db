from django.contrib import admin
from .models import ChatLog

@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'user_role', 'user_message', 'created_at')
    list_filter  = ('user_role',)
    search_fields = ('user_message', 'bot_response')
    readonly_fields = ('created_at',)
