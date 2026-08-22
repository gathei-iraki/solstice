# Solstice Events — Asynchronous Check-in Kiosk

This project is an event check-in kiosk built with Django. When an attendee's QR code is scanned, the application creates a badge-print job and publishes it asynchronously through RabbitMQ. The kiosk remains in a **Printing badge** state until the printer vendor confirms completion through a signed webhook. Only then does the kiosk display **Checked In**.

The repository includes a mock printer so the complete vendor workflow can be demonstrated locally without manually sending webhook requests.

## Requirements implemented

- Three test attendees are provided.
- Scanning creates an asynchronous badge-print request.
- The UI displays a pending state while printing is in progress.
- An attendee is marked as checked in only after a successful webhook.
- Duplicate scans reuse the original print job and do not print another badge.
- Duplicate and out-of-order callbacks cannot overwrite a completed job.
- Webhooks are authenticated using an HMAC-SHA256 signature.
- Successful and failed printer responses can both be demonstrated.

## Technology stack

- Python 3.13
- Django 5.2
- Celery 5.5
- RabbitMQ 3.13
- Kombu
- SQLite for local development
- HTML, CSS, and vanilla JavaScript
- Docker Compose for running RabbitMQ

## How the system works

```text
Kiosk browser
    │
    │ POST /api/scans/
    ▼
Django creates one pending PrintJob
    │
    │ Celery task
    ▼
Celery worker publishes the print request
    │
    ▼
RabbitMQ vendor.badge.print queue
    │
    ▼
Printer vendor (mock_printer during development)
    │
    │ signed completion webhook
    ▼
POST /webhooks/vendor/print-completed/
    │
    ▼
Django updates the job and attendee
    │
    │ frontend status polling
    ▼
Kiosk displays "Checked In" or "Print failed"
```

### Scan and job creation

The browser sends a QR code to `POST /api/scans/`. Django finds the attendee and creates a `PrintJob` with a `pending` status. The queue task is scheduled only after the database transaction commits successfully.

### Asynchronous printing

Celery publishes the print request to the durable `vendor.badge.print` RabbitMQ queue. The request contains the attendee details, job UUID, callback path, and an idempotency key.

The browser does not assume that submitting the scan means printing succeeded. It polls `GET /api/jobs/<job-id>/` and continues displaying **Printing badge** while the job is pending.

### Webhook confirmation

After printing, the vendor sends either a `succeeded` or `failed` callback. The webhook signature is checked before the payload is accepted. A successful callback sets `checked_in_at` and changes the job to `succeeded`. A failure records the printer error without checking in the attendee.

### Duplicate protection

`PrintJob.attendee` is a database `OneToOneField`, so an attendee can have at most one print job. Repeated scans return that existing job instead of publishing a new request. The job UUID is also sent as the vendor idempotency key.

Webhook updates lock the job row and only allow a pending job to enter a terminal state. A repeated or late callback is acknowledged but cannot change an already completed result.

## Project structure

```text
solstice/
├── checkin/
│   ├── management/commands/
│   │   ├── mock_printer.py
│   │   └── seed_attendees.py
│   ├── migrations/
│   ├── models.py
│   ├── tasks.py
│   ├── teste.py
│   ├── urls.py
│   └── views.py
├── solstice/
│   ├── celery.py
│   ├── settings.py
│   └── urls.py
├── static/checkin/
│   ├── kiosk.css
│   └── kiosk.js
├── templates/checkin/kiosk.html
├── docker-compose.yml
├── manage.py
└── requirements.txt
```

## Prerequisites

Install the following before running the project:

- Python 3.13 
- Docker with the Compose plugin
- 


## Installation

### 1. Open the project directory

```bash
cd solstice
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install the Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Apply the database migrations

```bash
python manage.py migrate
```

### 5. Create the demonstration attendees

```bash
python manage.py seed_attendees
```

The command is safe to run more than once and creates or updates these records:

| QR code | Name | Email |
|---|---|---|
| `SOL-001` | Ada Wairimu | `ada@gmail.com` |
| `SOL-002` | Grace Achieng | `grace@gmail.com` |
| `SOL-003` | Alan Kitur | `alan@gmail.com` |

## Running the project

The full demonstration uses RabbitMQ, Django, Celery, and the mock printer. Run each process in a separate terminal from the project directory.

### Terminal 1: RabbitMQ

```bash
docker compose up rabbitmq
```

To run RabbitMQ in the background instead, use:

```bash
docker compose up -d rabbitmq
```


### Terminal 2: Django web server

```bash
source .venv/bin/activate
python manage.py runserver
```

The kiosk will be available at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### Terminal 3: Celery worker

```bash
source .venv/bin/activate
celery -A solstice worker --loglevel=info
```

The worker receives the task created by Django and publishes the badge request to the vendor queue.

### Terminal 4: Mock printer vendor

```bash
source .venv/bin/activate
python manage.py mock_printer
```

The mock printer consumes vendor queue messages, waits two seconds, and sends correctly signed success webhooks back to Django.

## Demonstrating the application

1. Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
2. Enter `SOL-001` and select **Check in**.
3. Observe the **Printing badge** pending state.
4. After approximately two seconds, observe **Checked In**.
5. Enter `SOL-001` again to demonstrate duplicate protection. The existing job is returned, and no second print request is published.
6. Repeat the process with `SOL-002` and `SOL-003`.

Watch the Celery and mock-printer terminals during the demonstration to see the asynchronous message flow.

### Make the pending state easier to observe

Stop the mock printer with `Ctrl+C`, then restart it with a longer delay:

```bash
python manage.py mock_printer --delay 5
```

### Simulate printer failure

Stop the normal mock printer and run:

```bash
python manage.py mock_printer --delay 3 --fail
```

Scan an attendee who does not already have a print job. The kiosk will first display **Printing badge**, then **Print failed**. The attendee will not be marked as checked in.

Each attendee intentionally has only one print job, including failed jobs. Use a different seeded attendee for each fresh success or failure demonstration.






