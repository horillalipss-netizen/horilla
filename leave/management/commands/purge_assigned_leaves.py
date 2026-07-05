"""
Delete all currently assigned (available) leaves.

Useful to reset accidental mass assignments (e.g. a leave type created with
employees selected assigns leave days to everyone).

Usage:
    python manage.py purge_assigned_leaves            # everything
    python manage.py purge_assigned_leaves --leave-type 3   # one leave type only
"""

from django.core.management.base import BaseCommand

from leave.models import AvailableLeave


class Command(BaseCommand):
    help = "Delete all assigned (available) leaves, optionally for one leave type."

    def add_arguments(self, parser):
        parser.add_argument(
            "--leave-type",
            type=int,
            default=None,
            help="Only purge assigned leaves of this leave type id.",
        )

    def handle(self, *args, **options):
        qs = AvailableLeave.objects.all()
        if options["leave_type"]:
            qs = qs.filter(leave_type_id=options["leave_type"])
        count = qs.count()
        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} assigned leave record(s).")
        )
