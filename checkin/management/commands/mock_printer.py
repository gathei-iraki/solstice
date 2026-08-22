import hashlib
import hmac
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Connection, Consumer, Exchange, Queue


class Command(BaseCommand):
    help = "Run a mock badge-printer vendor"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=2,
            help="Seconds taken to print each badge",
        )

        parser.add_argument(
            "--fail",
            action="store_true",
            help="Simulate failed print jobs",
        )

        parser.add_argument(
            "--django-url",
            default="http://127.0.0.1:8000",
            help="Base URL of the Django server",
        )

    def handle(self, *args, **options):
        self.delay = options["delay"]
        self.should_fail = options["fail"]
        self.django_url = options["django_url"].rstrip("/")

        exchange = Exchange(
            settings.VENDOR_EXCHANGE,
            type="direct",
            durable=True,
        )

        queue = Queue(
            settings.VENDOR_PRINT_QUEUE,
            exchange=exchange,
            routing_key="badge.print",
            durable=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Mock printer is waiting for badge requests..."
            )
        )

        with Connection(settings.CELERY_BROKER_URL) as connection:
            with Consumer(
                connection,
                queues=[queue],
                callbacks=[self.process_print_request],
                accept=["json"],
            ):
                while True:
                    try:
                        connection.drain_events(timeout=2)
                    except TimeoutError:
                        continue
                    except KeyboardInterrupt:
                        self.stdout.write("\nMock printer stopped.")
                        break

    def process_print_request(self, body, message):
        job_id = body.get("job_id")
        attendee = body.get("attendee", {})
        attendee_name = attendee.get("name", "Unknown attendee")

        self.stdout.write(
            f"Received badge request for {attendee_name}"
        )

        try:
            self.stdout.write(
                f"Printing badge for {self.delay} seconds..."
            )

            time.sleep(self.delay)

            if self.should_fail:
                payload = {
                    "job_id": job_id,
                    "status": "failed",
                    "error": "Mock printer failure",
                }
            else:
                payload = {
                    "job_id": job_id,
                    "status": "succeeded",
                    "vendor_reference": f"mock-{job_id}",
                }

            self.send_webhook(payload)

        except Exception as error:
            # Requeue the RabbitMQ message so it can be retried.
            self.stderr.write(
                self.style.ERROR(
                    f"Could not process print job: {error}"
                )
            )
            message.reject(requeue=True)
            return

        # Remove the message only after the webhook succeeds.
        message.ack()

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed badge request for {attendee_name}"
            )
        )

    def send_webhook(self, payload):
        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode()

        signature = hmac.new(
            settings.VENDOR_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        webhook_url = (
            f"{self.django_url}"
            "/webhooks/vendor/print-completed/"
        )

        request = Request(
            webhook_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Vendor-Signature": signature,
            },
        )

        try:
            with urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"Webhook returned HTTP {response.status}"
                    )
        except URLError as error:
            raise RuntimeError(
                f"Could not reach webhook: {error}"
            ) from error