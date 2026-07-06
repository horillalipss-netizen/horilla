from django.test import TestCase

from employee.models import (
    Employee,
    KnowledgeComment,
    KnowledgeDocument,
    KnowledgeSpace,
)
from employee.templatetags.knowledge_tags import kb_richtext


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
