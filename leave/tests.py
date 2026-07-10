from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from employee.models import Employee
from horilla import horilla_middlewares
from leave.models import (
    LeaveRequest,
    LeaveType,
    LeaveTypeUsageRestriction,
)


class DummyUser:
    is_authenticated = False
    is_anonymous = True
    is_superuser = False


class DummyRequest:
    """Minimal request stand-in for model code that reads thread locals."""

    def __init__(self):
        self.session = {}
        self.user = DummyUser()


class LeaveTypeUsageRestrictionTestCase(TestCase):
    """
    Tests for the per-employee consecutive leave days restriction
    (LeaveRequest.check_leave_type_usage_restrictions).
    """

    def setUp(self):
        horilla_middlewares._thread_locals.request = DummyRequest()
        self.employee = Employee.objects.create(
            employee_first_name="Olga",
            employee_last_name="Test",
            email="olga.test@example.com",
            phone="123456789",
        )
        self.vacation = LeaveType.objects.create(name="Vacation", payment="paid")
        self.day_off = LeaveType.objects.create(name="Day off", payment="paid")
        self.restriction = LeaveTypeUsageRestriction.objects.create(
            employee_id=self.employee,
            max_consecutive_days=3,
            valid_until=date(2026, 8, 1),
        )
        self.restriction.leave_type_ids.set([self.vacation, self.day_off])

    def build_request(self, leave_type, start, end):
        return LeaveRequest(
            employee_id=self.employee,
            leave_type_id=leave_type,
            start_date=start,
            end_date=end,
            description="test",
        )

    def test_within_limit_passes(self):
        request = self.build_request(
            self.vacation, date(2026, 7, 13), date(2026, 7, 15)
        )
        request.check_leave_type_usage_restrictions()  # should not raise

    def test_over_limit_blocked(self):
        request = self.build_request(
            self.vacation, date(2026, 7, 13), date(2026, 7, 16)
        )
        with self.assertRaises(ValidationError):
            request.check_leave_type_usage_restrictions()

    def test_adjacent_requests_counted_together(self):
        # Existing approved 2-day vacation: 13-14.07
        LeaveRequest.objects.create(
            employee_id=self.employee,
            leave_type_id=self.vacation,
            start_date=date(2026, 7, 13),
            end_date=date(2026, 7, 14),
            description="existing",
            status="approved",
        )
        # New adjacent 2-day day-off 15-16.07 -> run of 4 > 3
        request = self.build_request(self.day_off, date(2026, 7, 15), date(2026, 7, 16))
        with self.assertRaises(ValidationError):
            request.check_leave_type_usage_restrictions()

    def test_non_adjacent_requests_pass(self):
        LeaveRequest.objects.create(
            employee_id=self.employee,
            leave_type_id=self.vacation,
            start_date=date(2026, 7, 13),
            end_date=date(2026, 7, 14),
            description="existing",
            status="approved",
        )
        # Gap on 15.07 -> separate run of 2 days
        request = self.build_request(self.day_off, date(2026, 7, 16), date(2026, 7, 17))
        request.check_leave_type_usage_restrictions()  # should not raise

    def test_rejected_requests_not_counted(self):
        LeaveRequest.objects.create(
            employee_id=self.employee,
            leave_type_id=self.vacation,
            start_date=date(2026, 7, 13),
            end_date=date(2026, 7, 14),
            description="existing",
            status="rejected",
        )
        request = self.build_request(self.day_off, date(2026, 7, 15), date(2026, 7, 16))
        request.check_leave_type_usage_restrictions()  # should not raise

    def test_unrestricted_leave_type_passes(self):
        sick = LeaveType.objects.create(name="Sick", payment="paid")
        request = self.build_request(sick, date(2026, 7, 13), date(2026, 7, 20))
        request.check_leave_type_usage_restrictions()  # should not raise

    def test_days_after_valid_until_not_counted(self):
        # 30.07 - 05.08: only 30.07, 31.07, 01.08 fall within the window -> 3 <= 3
        request = self.build_request(self.vacation, date(2026, 7, 30), date(2026, 8, 5))
        request.check_leave_type_usage_restrictions()  # should not raise

    def test_request_fully_after_valid_until_passes(self):
        request = self.build_request(self.vacation, date(2026, 8, 10), date(2026, 8, 20))
        request.check_leave_type_usage_restrictions()  # should not raise

    def test_other_employee_not_affected(self):
        other = Employee.objects.create(
            employee_first_name="Ivan",
            employee_last_name="Test",
            email="ivan.test@example.com",
            phone="987654321",
        )
        request = LeaveRequest(
            employee_id=other,
            leave_type_id=self.vacation,
            start_date=date(2026, 7, 13),
            end_date=date(2026, 7, 20),
            description="test",
        )
        request.check_leave_type_usage_restrictions()  # should not raise

class OnLeavePanelAccessTestCase(TestCase):
    """The dashboard "On Leave" panel is visible to every employee."""

    def test_regular_employee_can_view_on_leave_panel(self):
        from django.urls import reverse

        employee = Employee.objects.create(
            employee_first_name="Panel",
            employee_last_name="Viewer",
            email="panel.viewer@example.com",
            phone="123456789",
        )
        user = employee.employee_user_id
        user.is_new_employee = False
        user.save()
        self.client.force_login(user)
        response = self.client.get(reverse("employee-leave"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "leave/dashboard/on_leave.html")

    def test_on_leave_panel_not_limited_by_company(self):
        """The panel shows everyone on leave even when the viewer's session is
        scoped to a company and the leave-taker's work info has no company."""
        from django.urls import reverse

        from base.models import Company

        horilla_middlewares._thread_locals.request = DummyRequest()
        company = Company.objects.create(
            company="TOV Test",
            hq=True,
            address="Kyiv",
            country="Ukraine",
            state="Kyiv",
            city="Kyiv",
            zip="01001",
        )
        viewer = Employee.objects.create(
            employee_first_name="Scoped",
            employee_last_name="Viewer",
            email="scoped.viewer@example.com",
            phone="123456789",
        )
        viewer_user = viewer.employee_user_id
        viewer_user.is_new_employee = False
        viewer_user.save()
        viewer_wi = viewer.employee_work_info
        viewer_wi.company_id = company
        viewer_wi.save()
        onleave = Employee.objects.create(
            employee_first_name="Vasyl",
            employee_last_name="Companyless",
            email="vasyl.companyless@example.com",
            phone="123456789",
        )
        vacation = LeaveType.objects.create(name="Vacation2", payment="paid")
        LeaveRequest.objects.create(
            employee_id=onleave,
            leave_type_id=vacation,
            start_date=date.today(),
            end_date=date.today(),
            description="today",
            status="approved",
        )
        self.client.force_login(viewer_user)
        session = self.client.session
        session["selected_company"] = str(company.id)
        session.save()
        response = self.client.get(reverse("employee-leave"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vasyl")
