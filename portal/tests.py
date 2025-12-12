from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Client, Lead, RolePermission
from .permissions import get_permissions_for_user

User = get_user_model()


class PermissionGuardTests(TestCase):
    def setUp(self):
        self.password = 'test-pass-123'

    def test_viewer_cannot_access_documents_module(self):
        user = User.objects.create_user(username='viewer', password=self.password, role=User.Roles.VIEWER)
        # Simulate legacy permission rows that incorrectly allowed docs for viewers
        RolePermission.objects.update_or_create(role=User.Roles.VIEWER, defaults={'docs': True})

        self.client.login(username='viewer', password=self.password)
        resp = self.client.get(reverse('document_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_architect_without_invoice_perm_is_redirected(self):
        user = User.objects.create_user(username='arch', password=self.password, role=User.Roles.ARCHITECT)
        # Explicitly disable invoices for this role
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'invoices': False})

        self.client.login(username='arch', password=self.password)
        resp = self.client.get(reverse('invoice_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_project_routes_enforce_module_permission(self):
        user = User.objects.create_user(username='viewer2', password=self.password, role=User.Roles.VIEWER)
        # Viewer has projects True by default; disable to confirm guard blocks access
        RolePermission.objects.update_or_create(role=User.Roles.VIEWER, defaults={'projects': False})
        self.client.login(username='viewer2', password=self.password)

        resp = self.client.get(reverse('project_detail', args=[1]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_lead_convert_requires_leads_permission(self):
        user = User.objects.create_user(username='leadless', password=self.password, role=User.Roles.ARCHITECT)
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'leads': False})
        client = Client.objects.create(name='Test Client')
        lead = Lead.objects.create(client=client, title='Test Lead', created_by=user)

        self.client.login(username='leadless', password=self.password)
        resp = self.client.get(reverse('lead_convert', args=[lead.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_won_lead_without_project_can_be_converted(self):
        user = User.objects.create_user(username='arch2', password=self.password, role=User.Roles.ARCHITECT)
        RolePermission.objects.update_or_create(role=User.Roles.ARCHITECT, defaults={'leads': True})
        client = Client.objects.create(name='Test Client')
        lead = Lead.objects.create(
            client=client,
            title='Won Lead',
            status=Lead.Status.WON,
            created_by=user,
        )

        self.client.login(username='arch2', password=self.password)
        resp = self.client.get(reverse('lead_convert', args=[lead.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_alias_role_inherits_base_permissions_when_missing_row(self):
        RolePermission.objects.update_or_create(
            role=User.Roles.ARCHITECT,
            defaults={'clients': False, 'projects': True},
        )
        RolePermission.objects.filter(role=User.Roles.SENIOR_ARCHITECT).delete()
        user = User.objects.create_user(
            username='senior_arch',
            password=self.password,
            role=User.Roles.SENIOR_ARCHITECT,
        )

        perms = get_permissions_for_user(user)
        self.assertFalse(perms['clients'])
        self.assertTrue(perms['projects'])
