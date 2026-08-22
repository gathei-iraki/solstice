from celery import shared_task
from django.conf import settings
from django.utils import timezone
from kombu import Connection, Exchange, Producer, Queue

from .models import PrintJob


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=8,
)
def publish_badge_request(self, job_id):
    job = PrintJob.objects.select_related("attendee").get(
        pk=job_id
    )

    # Do not publish jobs that are complete or already published.
    if (
        job.status != PrintJob.Status.PENDING
        or job.published_at is not None
    ):
        return

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

    payload = {
        "job_id": str(job.id),

        # The vendor should use this to ignore duplicate messages.
        "idempotency_key": str(job.id),

        "attendee": {
            "name": job.attendee.name,
            "email": job.attendee.email,
        },

        "callback_url": (
            "/webhooks/vendor/print-completed/"
        ),
    }

    with Connection(settings.CELERY_BROKER_URL) as connection:
        producer = Producer(connection)

        producer.publish(
            payload,
            exchange=exchange,
            routing_key="badge.print",
            declare=[queue],
            serializer="json",
            delivery_mode=2,
            retry=True,
        )

    PrintJob.objects.filter(
        pk=job.id,
        published_at__isnull=True,
    ).update(
        published_at=timezone.now()
    )