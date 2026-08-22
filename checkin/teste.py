import hashlib
import hmac
import json
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from .models import Attendee, PrintJob


class CheckinFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        names = ("Ada", "Grace", "Alan")

        for number, name in enumerate(names, 1):
            Attendee.objects.create(
                qr_code=f"SOL-00{number}",
                name=name,
                email=f"{name.lower()}@example.com",
            )

    def scan(self, qr_code):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("scan"),
                {"qr_code": qr_code},
                content_type="application/json",
            )

    @patch("checkin.views.publish_badge_request.delay")
    def test_three_attendees_create_three_jobs(self, delay):
        for number in range(1, 4):
            response = self.scan(f"SOL-00{number}")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json()["status"],
                "pending",
            )

        self.assertEqual(PrintJob.objects.count(), 3)
        self.assertEqual(delay.call_count, 3)

    @patch("checkin.views.publish_badge_request.delay")
    def test_duplicate_scan_reuses_job(self, delay):
        first = self.scan("SOL-001").json()
        second = self.scan("SOL-001").json()

        self.assertEqual(
            first["job_id"],
            second["job_id"],
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(PrintJob.objects.count(), 1)
        self.assertEqual(delay.call_count, 1)

    @patch("checkin.views.publish_badge_request.delay")
    def test_successful_webhook_checks_in_attendee(
        self,
        delay,
    ):
        job_id = self.scan("SOL-002").json()["job_id"]

        response = self.send_webhook(
            {
                "job_id": job_id,
                "status": "succeeded",
                "vendor_reference": "print-42",
            }
        )

        self.assertEqual(response.status_code, 200)

        job = PrintJob.objects.get(pk=job_id)
        attendee = Attendee.objects.get(
            qr_code="SOL-002"
        )

        self.assertEqual(
            job.status,
            PrintJob.Status.SUCCEEDED,
        )
        self.assertIsNotNone(attendee.checked_in_at)

    @patch("checkin.views.publish_badge_request.delay")
    def test_late_failure_cannot_overwrite_success(
        self,
        delay,
    ):
        job_id = self.scan("SOL-003").json()["job_id"]

        self.send_webhook(
            {
                "job_id": job_id,
                "status": "succeeded",
            }
        )

        late_response = self.send_webhook(
            {
                "job_id": job_id,
                "status": "failed",
                "error": "Late failure",
            }
        )

        self.assertTrue(
            late_response.json()["duplicate"]
        )

        job = PrintJob.objects.get(pk=job_id)

        self.assertEqual(
            job.status,
            PrintJob.Status.SUCCEEDED,
        )

    def test_invalid_webhook_signature_is_rejected(self):
        response = self.client.post(
            reverse("vendor-webhook"),
            b"{}",
            content_type="application/json",
            HTTP_X_VENDOR_SIGNATURE="wrong",
        )

        self.assertEqual(response.status_code, 401)

    def send_webhook(self, payload):
        body = json.dumps(payload).encode()

        signature = hmac.new(
            settings.VENDOR_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        return self.client.post(
            reverse("vendor-webhook"),
            body,
            content_type="application/json",
            HTTP_X_VENDOR_SIGNATURE=signature,
        )