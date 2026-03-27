"""
Payroll Validation Agent (Type 13).

Pre-validates payroll runs by checking attendance completeness,
salary anomalies, duplicate employees, and deduction coherence.
"""

import logging
from decimal import Decimal

from django.db.models import Count, Sum, Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.hrpayroll.models import (
    Employee,
    PayrollRun,
    PayrollEntry,
    AttendanceRecord,
    PayrollPeriod,
    AttendanceTypeCode,
)

logger = logging.getLogger(__name__)


@register_agent
class PayrollValidationAgent(BaseAgent):
    """Pre-validates payroll runs before approval."""

    AGENT_TYPE = AgentTypeCode.PAYROLL_VALIDATION

    def execute(self, *, payroll_run_id: str, **kwargs) -> dict:
        salary_change_threshold = Decimal(str(self.config.get('salary_change_threshold', 0.20)))
        total_change_threshold = Decimal(str(self.config.get('total_change_threshold', 0.15)))

        run = PayrollRun.objects.select_related('payrollperiodid').get(
            payrollrunid=payroll_run_id
        )
        period = run.payrollperiodid
        entries = PayrollEntry.objects.filter(
            payrollrunid=run
        ).select_related('employeeid')

        errors = []
        warnings = []
        anomalies = []

        employee_ids = list(entries.values_list('employeeid', flat=True))

        # 1. Check attendance completeness
        period_start = period.startdate
        period_end = period.enddate
        total_days = (period_end - period_start).days + 1

        for entry in entries:
            emp = entry.employeeid
            attendance_count = AttendanceRecord.objects.filter(
                employeeid=emp.employeeid,
                attendancedate__gte=period_start,
                attendancedate__lte=period_end,
            ).count()

            # Exclude weekends (approximate: 5/7 ratio)
            expected_workdays = int(total_days * 5 / 7)
            if attendance_count < expected_workdays * 0.8:
                errors.append({
                    'type': 'incomplete_attendance',
                    'employee_id': str(emp.employeeid),
                    'details': (
                        f"{emp.fullname}: {attendance_count} attendance records "
                        f"for {expected_workdays} expected workdays "
                        f"({period_start} to {period_end})"
                    ),
                })

        # 2. Detect salary changes >20% vs previous period
        previous_runs = PayrollRun.objects.filter(
            payrollperiodid__enddate__lt=period_start,
        ).order_by('-payrollperiodid__enddate')[:1]

        if previous_runs.exists():
            prev_run = previous_runs.first()
            prev_entries = {
                str(e.employeeid_id): e
                for e in PayrollEntry.objects.filter(
                    payrollrunid=prev_run
                ).select_related('employeeid')
            }

            for entry in entries:
                emp_key = str(entry.employeeid_id)
                if emp_key in prev_entries:
                    prev_entry = prev_entries[emp_key]
                    prev_net = prev_entry.netpay or Decimal('0')
                    curr_net = entry.netpay or Decimal('0')

                    if prev_net > 0:
                        change_pct = abs(curr_net - prev_net) / prev_net
                        if change_pct > salary_change_threshold:
                            warnings.append({
                                'type': 'salary_change',
                                'employee_id': str(entry.employeeid.employeeid),
                                'details': (
                                    f"{entry.employeeid.fullname}: net pay changed "
                                    f"from ${float(prev_net):,.2f} to ${float(curr_net):,.2f} "
                                    f"({float(change_pct * 100):.1f}% change)"
                                ),
                            })

        # 3. Check for duplicate employees across concurrent runs
        concurrent_runs = PayrollRun.objects.filter(
            payrollperiodid=period,
        ).exclude(payrollrunid=run.payrollrunid)

        for concurrent_run in concurrent_runs:
            concurrent_employees = set(
                PayrollEntry.objects.filter(
                    payrollrunid=concurrent_run
                ).values_list('employeeid', flat=True)
            )
            duplicates = set(employee_ids) & concurrent_employees
            for dup_id in duplicates:
                emp = Employee.objects.get(employeeid=dup_id)
                errors.append({
                    'type': 'duplicate_employee',
                    'employee_id': str(dup_id),
                    'details': (
                        f"{emp.fullname} appears in both run "
                        f"{run.runnumber} and {concurrent_run.runnumber}"
                    ),
                })

        # 4. Validate deduction/addition coherence
        for entry in entries:
            deductions = entry.deductions or []
            additions = entry.additions or []
            total_ded = sum(d.get('amount', 0) for d in deductions)
            total_add = sum(a.get('amount', 0) for a in additions)

            expected_net = float(entry.grosspay or 0) + total_add - total_ded
            actual_net = float(entry.netpay or 0)

            if abs(expected_net - actual_net) > 0.02:
                anomalies.append({
                    'type': 'calculation_mismatch',
                    'employee_id': str(entry.employeeid.employeeid),
                    'details': (
                        f"{entry.employeeid.fullname}: expected net "
                        f"${expected_net:,.2f} but found ${actual_net:,.2f}"
                    ),
                })

            if float(entry.grosspay or 0) > 0 and total_ded > float(entry.grosspay or 0):
                anomalies.append({
                    'type': 'deductions_exceed_gross',
                    'employee_id': str(entry.employeeid.employeeid),
                    'details': (
                        f"{entry.employeeid.fullname}: total deductions "
                        f"${total_ded:,.2f} exceed gross pay "
                        f"${float(entry.grosspay):,.2f}"
                    ),
                })

        # 5. Compare totals vs previous period
        comparison = None
        if previous_runs.exists():
            prev_run = previous_runs.first()
            prev_total = float(prev_run.totalnetpay or 0)
            curr_total = float(run.totalnetpay or 0)
            diff = curr_total - prev_total
            diff_pct = (diff / prev_total * 100) if prev_total else 0

            comparison = {
                'previous_run': prev_run.runnumber,
                'previous_total': prev_total,
                'current_total': curr_total,
                'difference': round(diff, 2),
                'difference_pct': round(diff_pct, 2),
            }

            if abs(diff_pct) > float(total_change_threshold * 100):
                warnings.append({
                    'type': 'total_change',
                    'employee_id': None,
                    'details': (
                        f"Total net pay changed {diff_pct:+.1f}% "
                        f"(${prev_total:,.2f} -> ${curr_total:,.2f})"
                    ),
                })

        is_valid = len(errors) == 0

        result = {
            'payroll_run_id': str(run.payrollrunid),
            'period': period.label,
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'anomalies': anomalies,
            'comparison': comparison,
        }

        # Create suggestion
        severity = SuggestionSeverity.INFO
        if errors:
            severity = SuggestionSeverity.CRITICAL
        elif warnings or anomalies:
            severity = SuggestionSeverity.WARNING

        self._create_suggestion(
            title=(
                f"Payroll {run.runnumber}: "
                + ("VALID" if is_valid else f"{len(errors)} errors found")
            ),
            description=(
                f"Validated {entries.count()} entries for period {period.label}. "
                f"Errors: {len(errors)}, Warnings: {len(warnings)}, "
                f"Anomalies: {len(anomalies)}."
            ),
            confidence=0.9 if is_valid else 0.95,
            severity=severity,
            suggested_action='approve_payroll' if is_valid else 'review_payroll',
            suggested_data=result,
        )

        return result
