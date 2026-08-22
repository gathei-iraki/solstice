import hashlib
import hmac
import json

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Attendee, PrintJob
from .tasks import publish_badge_request


def kiosk(request):
    return render(request, "checkin/kiosk.html")


def parse_json(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def job_response(job, duplicate=False):
    return JsonResponse(
        {
            "job_id": str(job.id),
            "attendee": job.attendee.name,
            "status": job.status,
            "message": job.get_status_display(),
            "duplicate": duplicate,
            "error": job.error_message,
        }
    )


@require_POST
def scan(request):
    data = parse_json(request)

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Invalid JSON"},
            status=400,
        )

    qr_code = data.get("qr_code", "").strip()

    if not qr_code:
        return JsonResponse(
            {"error": "qr_code is required"},
            status=400,
        )

    try:
        attendee = Attendee.objects.get(qr_code=qr_code)
    except Attendee.DoesNotExist:
        return JsonResponse(
            {"error": "Attendee not found"},
            status=404,
        )

    try:
        with transaction.atomic():
            job, created = PrintJob.objects.get_or_create(
                attendee=attendee
            )

            if created:
                transaction.on_commit(
                    lambda: publish_badge_request.delay(
                        str(job.id)
                    )
                )

    except IntegrityError:
        # Handles a concurrent request that created the job first.
        job = PrintJob.objects.get(attendee=attendee)
        created = False

    job = PrintJob.objects.select_related("attendee").get(
        pk=job.pk
    )

    return job_response(
        job,
        duplicate=not created,
    )


@require_GET
def job_status(request, job_id):
    try:
        job = PrintJob.objects.select_related(
            "attendee"
        ).get(pk=job_id)

    except PrintJob.DoesNotExist:
        return JsonResponse(
            {"error": "Print job not found"},
            status=404,
        )

    return job_response(job)


@csrf_exempt
@require_POST
def vendor_webhook(request):
    signature = request.headers.get(
        "X-Vendor-Signature",
        "",
    )

    expected_signature = hmac.new(
        settings.VENDOR_WEBHOOK_SECRET.encode(),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        signature,
        expected_signature,
    ):
        return JsonResponse(
            {"error": "Invalid signature"},
            status=401,
        )

    data = parse_json(request)

    if (
        not isinstance(data, dict)
        or data.get("status") not in {"succeeded", "failed"}
    ):
        return JsonResponse(
            {"error": "Invalid payload"},
            status=400,
        )

    try:
        with transaction.atomic():
            job = (
                PrintJob.objects
                .select_for_update()
                .select_related("attendee")
                .get(pk=data.get("job_id"))
            )

            # Never change a completed job again.
            if job.status != PrintJob.Status.PENDING:
                return JsonResponse(
                    {
                        "received": True,
                        "duplicate": True,
                    }
                )

            job.vendor_reference = str(
                data.get("vendor_reference", "")
            )[:100]

            job.completed_at = timezone.now()

            if data["status"] == "succeeded":
                job.status = PrintJob.Status.SUCCEEDED

                job.attendee.checked_in_at = job.completed_at
                job.attendee.save(
                    update_fields=["checked_in_at"]
                )

            else:
                job.status = PrintJob.Status.FAILED
                job.error_message = str(
                    data.get("error", "Printer failed")
                )

            job.save()

    except (PrintJob.DoesNotExist, ValueError, TypeError):
        return JsonResponse(
            {"error": "Unknown print job"},
            status=404,
        )

    return JsonResponse({"received": True})