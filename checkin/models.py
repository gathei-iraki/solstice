import uuid

from django.db import models


class Attendee(models.Model):
    qr_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    email = models.EmailField()
    checked_in_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class PrintJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Printing badge"
        SUCCEEDED = "succeeded", "Checked In"
        FAILED = "failed", "Print failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # One attendee can have only one print job.
    attendee = models.OneToOneField(
        Attendee,
        on_delete=models.CASCADE,
        related_name="print_job",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    published_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    vendor_reference = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.attendee.name}: {self.status}"