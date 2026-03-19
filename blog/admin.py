from typing import Any
from django.contrib import admin
from .models import Post, Category, AboutUs, Profile, Message, ContactMessage

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'content')
    search_fields = ('title', 'content')
    list_filter = ('category', 'created_at')

class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')
    search_fields = ('name', 'email', 'message')
    list_filter = ('created_at',)

# Register your models here.
admin.site.register(Post, PostAdmin)
admin.site.register(Category)
admin.site.register(AboutUs)
admin.site.register(Profile)
admin.site.register(Message)
admin.site.register(ContactMessage, ContactMessageAdmin)
