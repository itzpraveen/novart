from datetime import timedelta

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from portal.models import Invoice, Notification, Project, ReminderSetting, Task, User
from portal.notifications.whatsapp import send_text as send_whatsapp_text


class Command(BaseCommand):
    help = "Generate reminder notifications for tasks, handovers, and invoices."

    def handle(self, *args, **options):
        today = timezone.localdate()
        settings = ReminderSetting.objects.all()
        admins = list(User.objects.filter(role=User.Roles.ADMIN))
        total_notifications = 0

        for setting in settings:
            horizon = today + timedelta(days=setting.days_before)
            if setting.category == ReminderSetting.Category.TASK:
                total_notifications += self._handle_tasks(setting, today, horizon, admins)
            elif setting.category == ReminderSetting.Category.HANDOVER:
                total_notifications += self._handle_handover(setting, today, horizon, admins)
            elif setting.category == ReminderSetting.Category.INVOICE:
                total_notifications += self._handle_invoice_due(setting, today, horizon, admins)
            elif setting.category == ReminderSetting.Category.INVOICE_OVERDUE:
                total_notifications += self._handle_invoice_overdue(setting, today, admins)

        self.stdout.write(self.style.SUCCESS(f"Reminders processed. Notifications created: {total_notifications}"))

    def _notify(self, users, message, category, url=""):
        created = 0
        today = timezone.localdate()
        for user in users:
            if not user:
                continue
            already_sent = Notification.objects.filter(
                user=user,
                category=category,
                message=message,
                created_at__date=today,
            ).exists()
            if already_sent:
                continue
            Notification.objects.create(user=user, message=message, category=category, related_url=url)
            # Best-effort WhatsApp push if enabled and phone is present
            if user.phone:
                send_whatsapp_text(user.phone, message)
            created += 1
        return created

    def _recipients(self, setting, primary_user, admins):
        recipients = []
        if setting.send_to_assigned and primary_user:
            recipients.append(primary_user)
        if setting.send_to_admins:
            recipients.extend(admins)
        # remove duplicates
        seen = set()
        unique = []
        for user in recipients:
            if user and user.id not in seen:
                unique.append(user)
                seen.add(user.id)
        return unique

    def _handle_tasks(self, setting, today, horizon, admins):
        tasks = Task.objects.filter(
            due_date__isnull=False,
            due_date__lte=horizon,
            status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS],
        )
        count = 0
        for task in tasks:
            message = f'Task "{task.title}" is due on {task.due_date.strftime("%d-%m-%Y")}'
            url = reverse('my_tasks')
            recipients = self._recipients(setting, task.assigned_to, admins)
            count += self._notify(recipients, message, setting.category, url)
        return count

    def _handle_handover(self, setting, today, horizon, admins):
        projects = Project.objects.filter(expected_handover__isnull=False, expected_handover__lte=horizon)
        count = 0
        for project in projects:
            message = f'Handover for {project.code} is on {project.expected_handover.strftime("%d-%m-%Y")}'
            url = reverse('project_detail', args=[project.pk])
            recipients = self._recipients(setting, project.project_manager, admins)
            count += self._notify(recipients, message, setting.category, url)
        return count

    def _handle_invoice_due(self, setting, today, horizon, admins):
        invoices = Invoice.objects.filter(due_date__lte=horizon).exclude(status=Invoice.Status.PAID)
        count = 0
        for invoice in invoices:
            invoice.refresh_status(today=today)
            owner = invoice.project.project_manager if invoice.project else None
            message = f'Invoice {invoice.display_invoice_number} due on {invoice.due_date.strftime("%d-%m-%Y")}'
            url = reverse('invoice_list')
            recipients = self._recipients(setting, owner, admins)
            count += self._notify(recipients, message, setting.category, url)
        return count

    def _handle_invoice_overdue(self, setting, today, admins):
        invoices = Invoice.objects.filter(due_date__lt=today).exclude(status=Invoice.Status.PAID)
        count = 0
        for invoice in invoices:
            invoice.refresh_status(today=today)
            owner = invoice.project.project_manager if invoice.project else None
            message = f'Invoice {invoice.display_invoice_number} is overdue'
            recipients = self._recipients(setting, owner, admins)
            count += self._notify(recipients, message, setting.category, reverse('invoice_list'))
        return count
