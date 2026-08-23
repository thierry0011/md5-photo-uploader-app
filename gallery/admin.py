from django.contrib import admin

from .models import Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "description", "uploaded_at")
    readonly_fields = ("uploaded_at",)
