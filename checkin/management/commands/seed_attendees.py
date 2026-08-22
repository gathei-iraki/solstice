from django.core.management.base import BaseCommand

from checkin.models import Attendee


class Command(BaseCommand):
    help = "Create the three test attendees"

    def handle(self, *args, **options):
        attendees = [
            (
                "SOL-001",
                "Ada Wairimu",
                "ada@gmail.com",
            ),
            (
                "SOL-002",
                "Grace Achieng",
                "grace@gmail.com",
            ),
            (
                "SOL-003",
                "Alan Kitur",
                "alan@gmail.com",
            ),
        ]

        for qr_code, name, email in attendees:
            Attendee.objects.update_or_create(
                qr_code=qr_code,
                defaults={
                    "name": name,
                    "email": email,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Three attendees are ready."
            )
        )