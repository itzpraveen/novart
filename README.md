# StudioFlow – Architecture Operations Hub

StudioFlow is an internal operations tool for small Kerala-based architecture practices. It keeps client/lead data, live project tracking, field activity, documents, light-weight finance, and reminder automation in one reliable Django application.

## Stack & Rationale
- **Backend/UI**: Django 5 with Django templates – batteries-included admin, mature auth/ORM, fast forms and filters, and simple VPS deployment.
- **Database**: SQLite for local development; swap to PostgreSQL by changing `DATABASES` in `studioflow/settings.py`.
- **Frontend**: Server-rendered Bootstrap 5 templates – minimal JS, long-term maintainability.
- **Task Scheduling**: Django management command (`send_reminders`) hooked to cron or systemd timers.

## Features
- Clients/CRM with lead pipeline and single-click “convert to project”.
- Project hub with stage history, health, kanban board, and per-project finance snapshot.
- Task management (project kanban + “My tasks” cross-project view).
- Site visits & issue tracking with attachments, filters, and expenses.
- Finance lite: invoices, payments, cashbook ledger, and consolidated dashboard.
- Document register with metadata + uploads.
- Dashboard with pipeline, milestones, and financial highlights.
- Reminder automation for task deadlines, handovers, and invoices (due + overdue) generating in-app notifications.

## Getting Started
### Prerequisites
- Python 3.11+ (repo tested with 3.13)
- `pip` and `venv`

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000 and log in with the user created above.

### Environment Variables
- `DJANGO_SECRET_KEY`: override the default dev key.
- `DJANGO_ALLOWED_HOSTS`: comma separated hosts (e.g. `studio.example.com,127.0.0.1`).
- `DATABASE_URL` if you swap to a different database backend (update `DATABASES`).

### Seed Sample Data (optional)
```bash
python manage.py seed_demo
```
Creates a demo client, project, visit, invoice, cashbook entry, reminder defaults, and a few tasks tied to the first user.

### Reminders / Automation
Reminders run through a management command; schedule it with cron:

```bash
# Every morning at 7 AM IST
0 7 * * * /path/to/.venv/bin/python /path/to/manage.py send_reminders >> /var/log/studioflow-reminders.log 2>&1
```

The command inspects configured `ReminderSetting` records (pre-seeded for task due dates, handovers, invoice due, and overdue) and writes in-app notifications to the assigned staff + admins.

## Useful Commands
- `python manage.py createsuperuser` – add admin.
- `python manage.py shell` – ad-hoc inspection.
- `python manage.py collectstatic` – when deploying behind a web server.
- `python manage.py send_reminders` – manual run of notifications.

## Project Structure (key folders)
```
studioflow/         # Django project settings/urls
portal/             # Application logic (models, views, forms, commands)
templates/          # Base + portal templates
static/             # Custom static assets placeholder
media/              # Uploaded documents/attachments
```

## Roles & Access
- User roles live on the custom user model (`portal.User`). Use Django admin to flag users as Admin / Architect / Site Engineer / Finance and to assign project managers.

## Testing & Health
Run Django’s system checks:
```bash
python manage.py check
```

For production, hook up HTTPS, configure a persistent database, and point static/media roots to the web server (nginx/Apache) as per Django deployment docs.
