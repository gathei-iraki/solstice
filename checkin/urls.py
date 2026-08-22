from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.kiosk,
        name="kiosk",
    ),
    path(
        "api/scans/",
        views.scan,
        name="scan",
    ),
    path(
        "api/jobs/<uuid:job_id>/",
        views.job_status,
        name="job-status",
    ),
    path(
        "webhooks/vendor/print-completed/",
        views.vendor_webhook,
        name="vendor-webhook",
    ),
]