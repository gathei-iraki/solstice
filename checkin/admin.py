from django.contrib import admin

from .models import Attendee, PrintJob


@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "qr_code", "checked_in_at")
    search_fields = ("name", "email", "qr_code")


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attendee",
        "status",
        "published_at",
        "completed_at",
    )
    list_filter = ("status",)
    search_fields = ("attendee__name", "attendee__qr_code")