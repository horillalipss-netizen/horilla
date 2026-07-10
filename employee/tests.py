from django.test import TestCase
from django.urls import reverse

from base.access import kb_accessible_spaces, kb_space_level
from employee.models import (
    Employee,
    EmployeeWorkInformation,
    KnowledgeComment,
    KnowledgeDocument,
    KnowledgeSpace,
)
from employee.templatetags.knowledge_tags import kb_richtext
from horilla import horilla_middlewares


class DummyUser:
    is_authenticated = False
    is_anonymous = True
    is_superuser = False


class DummyRequest:
    """Minimal request stand-in for model code that reads thread locals."""

    def __init__(self):
        self.session = {}
        self.user = DummyUser()


def reset_thread_locals():
    """Drop any stale request left in thread locals by a previous test."""
    horilla_middlewares._thread_locals.request = DummyRequest()


def make_employee(first, last, email, phone="123456789"):
    employee = Employee.objects.create(
        employee_first_name=first,
        employee_last_name=last,
        email=email,
        phone=phone,
    )
    user = employee.employee_user_id
    user.is_new_employee = False
    user.save()
    return employee


class KnowledgeRichTextTestCase(TestCase):
    """Tests for the kb_richtext template filter (clickable links)."""

    def test_urls_become_clickable_links(self):
        html = kb_richtext("see https://example.com/x?a=1")
        self.assertIn('href="https://example.com/x?a=1"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_html_is_escaped(self):
        html = kb_richtext("<script>alert(1)</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_line_breaks_preserved(self):
        self.assertIn("<br>", kb_richtext("line1\nline2"))

    def test_empty_value(self):
        self.assertEqual(kb_richtext(None), "")
        self.assertEqual(kb_richtext(""), "")


class KnowledgeCommentEditTestCase(TestCase):
    """Tests for editing knowledge base comments."""

    def setUp(self):
        self.space = KnowledgeSpace.objects.create(title="Space", is_public=True)
        self.document = KnowledgeDocument.objects.create(
            space_id=self.space, title="Doc"
        )
        self.comment = KnowledgeComment.objects.create(
            document_id=self.document, comment="old text"
        )
        self.employee = Employee.objects.create(
            employee_first_name="Test",
            employee_last_name="User",
            email="kb.test@example.com",
            phone="123456789",
        )
        user = self.employee.employee_user_id
        user.is_new_employee = False
        user.save()

    def test_edit_comment_updates_text(self):
        self.client.force_login(self.employee.employee_user_id)
        response = self.client.post(
            f"/employee/knowledge-comment-edit/{self.comment.id}/",
            {"comment": "new text"},
        )
        self.assertEqual(
            response.status_code, 302, response.headers.get("Location")
        )
        self.assertEqual(
            response.headers.get("Location"),
            f"/employee/knowledge-space/{self.space.id}/",
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.comment, "new text")

    def test_space_page_renders_clickable_links(self):
        self.comment.comment = "see https://example.com/doc"
        self.comment.save()
        self.client.force_login(self.employee.employee_user_id)
        response = self.client.get(f"/employee/knowledge-space/{self.space.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="https://example.com/doc"')
        self.assertContains(response, f"commentEdit{self.comment.id}")

    def test_edit_comment_ignores_empty_text(self):
        self.client.force_login(self.employee.employee_user_id)
        self.client.post(
            f"/employee/knowledge-comment-edit/{self.comment.id}/",
            {"comment": "   "},
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.comment, "old text")

class KnowledgeManagerAccessTestCase(TestCase):
    """Managers with at least one subordinate may create KB spaces/documents."""

    def setUp(self):
        reset_thread_locals()
        self.manager = make_employee("Man", "Ager", "manager@example.com")
        self.subordinate = make_employee("Sub", "Ordinate", "sub@example.com")
        self.regular = make_employee("Reg", "Ular", "regular@example.com")
        # Work info is auto-created together with the employee.
        work_info = EmployeeWorkInformation.objects.get(
            employee_id=self.subordinate
        )
        work_info.reporting_manager_id = self.manager
        work_info.save()

    def test_manager_can_create_space(self):
        self.client.force_login(self.manager.employee_user_id)
        response = self.client.post(
            reverse("knowledge-space-create"), {"title": "Team docs"}
        )
        self.assertEqual(response.status_code, 302)
        space = KnowledgeSpace.objects.filter(title="Team docs").first()
        self.assertIsNotNone(space)
        self.assertEqual(space.created_by_id, self.manager.employee_user_id.id)

    def test_regular_employee_cannot_create_space(self):
        self.client.force_login(self.regular.employee_user_id)
        self.client.post(reverse("knowledge-space-create"), {"title": "Nope"})
        self.assertFalse(KnowledgeSpace.objects.filter(title="Nope").exists())

    def test_creator_has_full_level_and_sees_own_private_space(self):
        space = KnowledgeSpace.objects.create(
            title="Own", is_public=False, created_by=self.manager.employee_user_id
        )
        user = self.manager.employee_user_id
        self.assertEqual(kb_space_level(user, space), "full")
        self.assertIn(space, kb_accessible_spaces(user))
        # Another employee has no access to it
        self.assertIsNone(kb_space_level(self.regular.employee_user_id, space))
        self.assertNotIn(
            space, kb_accessible_spaces(self.regular.employee_user_id)
        )

    def test_manager_cannot_delete_others_space(self):
        space = KnowledgeSpace.objects.create(
            title="HR space", is_public=True,
            created_by=self.regular.employee_user_id,
        )
        self.client.force_login(self.manager.employee_user_id)
        self.client.get(reverse("knowledge-space-delete", args=[space.id]))
        self.assertTrue(KnowledgeSpace.objects.filter(id=space.id).exists())

    def test_creator_can_delete_own_space(self):
        self.client.force_login(self.manager.employee_user_id)
        self.client.post(reverse("knowledge-space-create"), {"title": "Mine"})
        space = KnowledgeSpace.objects.get(title="Mine")
        self.client.get(reverse("knowledge-space-delete", args=[space.id]))
        self.assertFalse(KnowledgeSpace.objects.filter(id=space.id).exists())

    def test_creator_can_add_document(self):
        self.client.force_login(self.manager.employee_user_id)
        self.client.post(reverse("knowledge-space-create"), {"title": "Mine"})
        space = KnowledgeSpace.objects.get(title="Mine")
        response = self.client.post(
            reverse("knowledge-document-create", args=[space.id]),
            {"title": "Doc 1"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(space.documents.filter(title="Doc 1").exists())


class KnowledgeDocumentOrderingTestCase(TestCase):
    """Documents are listed oldest-first; new ones append at the bottom."""

    def test_documents_oldest_first(self):
        reset_thread_locals()
        space = KnowledgeSpace.objects.create(title="Space", is_public=True)
        first = KnowledgeDocument.objects.create(space_id=space, title="First")
        second = KnowledgeDocument.objects.create(space_id=space, title="Second")
        self.assertEqual(list(space.documents.all()), [first, second])


class EmployeeListAccessTestCase(TestCase):
    """Every employee sees the full employee list (CEO hidden from non-HR)."""

    def setUp(self):
        reset_thread_locals()
        self.regular = make_employee("Reg", "Ular", "regular2@example.com")
        self.colleague = make_employee("Col", "League", "colleague@example.com")
        self.ceo = make_employee("Big", "Boss", "ceo@example.com")
        self.ceo.is_ceo = True
        self.ceo.save()

    def test_regular_employee_sees_everyone_but_ceo(self):
        self.client.force_login(self.regular.employee_user_id)
        response = self.client.get(
            reverse("employee-view-list"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "League")
        self.assertNotContains(response, "Boss")

    def test_regular_employee_sees_card_view(self):
        self.client.force_login(self.regular.employee_user_id)
        response = self.client.get(
            reverse("employee-view-card"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "League")
        self.assertNotContains(response, "Boss")

    def test_manager_sees_everyone_with_accessibility_row_present(self):
        """A reporting manager must see the full list even when a
        DefaultAccessibility row for 'employee_view' exists (this row used to
        trigger subordinate-only filtering inside EmployeeFilter)."""
        from accessibility.models import DefaultAccessibility

        DefaultAccessibility.objects.create(
            feature="employee_view", filter={"feature": ["employee_view"]}
        )
        manager = make_employee("List", "Manager", "list.manager@example.com")
        subordinate_wi = EmployeeWorkInformation.objects.get(
            employee_id=self.colleague
        )
        subordinate_wi.reporting_manager_id = manager
        subordinate_wi.save()
        self.client.force_login(manager.employee_user_id)
        response = self.client.get(
            reverse("employee-view-list"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        # Sees the subordinate...
        self.assertContains(response, "League")
        # ...and a non-subordinate employee too.
        self.assertContains(response, "Ular")

    def test_company_scoped_session_does_not_hide_employees(self):
        """A viewer whose session is scoped to a company still sees employees
        whose work information has no (or another) company."""
        from base.models import Company

        company = Company.objects.create(
            company="TOV Test",
            hq=True,
            address="Kyiv",
            country="Ukraine",
            state="Kyiv",
            city="Kyiv",
            zip="01001",
        )
        viewer_wi = EmployeeWorkInformation.objects.get(employee_id=self.regular)
        viewer_wi.company_id = company
        viewer_wi.save()
        # self.colleague keeps an empty company in work information.
        self.client.force_login(self.regular.employee_user_id)
        session = self.client.session
        session["selected_company"] = str(company.id)
        session.save()
        response = self.client.get(
            reverse("employee-view-list"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "League")


class SelfProfileEditTestCase(TestCase):
    """Every employee may always edit their own profile (no feature flag)."""

    def test_employee_updates_own_profile(self):
        reset_thread_locals()
        employee = make_employee("Self", "Editor", "self.editor@example.com")
        self.client.force_login(employee.employee_user_id)
        response = self.client.post(
            reverse("edit-profile"),
            {
                "employee_first_name": "Updated",
                "employee_last_name": "Editor",
                "email": "self.editor@example.com",
                "phone": "123456789",
                "gender": "male",
                "qualification": "Master",
                "children_info": "Two kids",
                "np_branch": "Branch 42",
                "np_postomat": "Postomat 7",
            },
        )
        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.employee_first_name, "Updated")
        self.assertEqual(employee.qualification, "Master")
        self.assertEqual(employee.children_info, "Two kids")
        self.assertEqual(employee.np_branch, "Branch 42")
        self.assertEqual(employee.np_postomat, "Postomat 7")

    def test_employee_updates_own_bank_details(self):
        from employee.models import EmployeeBankDetails

        reset_thread_locals()
        employee = make_employee("Bank", "Editor", "bank.editor@example.com")
        self.client.force_login(employee.employee_user_id)
        response = self.client.post(
            reverse("edit-profile"),
            {
                "bank_info_submit": "1",
                "iban": "UA213223130000026007233566001",
                "rnokpp": "1234567890",
                "payment_purpose": "FOP payment",
                "fop_maintained": "on",
                "bank_name": "PrivatBank",
                "card_number": "4149499912345678",
                "wallet_number": "TRC20-abc",
                "wallet_currency": "USDT",
            },
        )
        self.assertEqual(response.status_code, 200)
        bank = EmployeeBankDetails.objects.get(employee_id=employee)
        self.assertEqual(bank.iban, "UA213223130000026007233566001")
        self.assertEqual(bank.rnokpp, "1234567890")
        self.assertEqual(bank.payment_purpose, "FOP payment")
        self.assertTrue(bank.fop_maintained)
        self.assertEqual(bank.bank_name, "PrivatBank")
        self.assertEqual(bank.card_number, "4149499912345678")
        self.assertEqual(bank.wallet_number, "TRC20-abc")
        self.assertEqual(bank.wallet_currency, "USDT")
