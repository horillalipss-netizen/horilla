"""
payroll/sidebar.py

"""

from django.urls import reverse
from django.utils.translation import gettext_lazy as trans

# Renamed from "Payroll" to "Compensation" per the access spec.
MENU = trans("Compensation")
IMG_SRC = "images/ui/wallet-outline.svg"

SUBMENUS = [
    {
        "menu": trans("Dashboard"),
        "redirect": reverse("view-payroll-dashboard"),
        # HR only.
        "accessibility": "base.access.sidebar_hr_only",
        "hr_only": True,
    },
    {
        "menu": trans("Contract"),
        "redirect": reverse("view-contract"),
        # HR only.
        "accessibility": "base.access.sidebar_hr_only",
        "hr_only": True,
    },
    {
        "menu": trans("Allowances"),
        "redirect": reverse("view-allowance"),
        # HR only.
        "accessibility": "base.access.sidebar_hr_only",
        "hr_only": True,
    },
    {
        "menu": trans("Deductions"),
        "redirect": reverse("view-deduction"),
        # Disabled for everyone.
        "accessibility": "base.access.sidebar_disabled",
    },
    {
        "menu": trans("Payslips"),
        "redirect": reverse("view-payslip"),
        # Disabled for everyone.
        "accessibility": "base.access.sidebar_disabled",
    },
    {
        "menu": trans("Loan / Advanced Salary"),
        "redirect": reverse("view-loan"),
        # Disabled for everyone.
        "accessibility": "base.access.sidebar_disabled",
    },
    {
        # Renamed from "Encashments & Reimbursements" to "Well-being".
        # Visible to everyone: non-HR may only request a reimbursement for
        # themselves; HR can create for anyone and approves all requests.
        "menu": trans("Well-being"),
        "redirect": reverse("view-reimbursement"),
    },
    {
        "menu": trans("Federal Tax"),
        "redirect": reverse("filing-status-view"),
        # Disabled for everyone.
        "accessibility": "base.access.sidebar_disabled",
    },
]
