"""
Attendance Anomaly Agent (Type 14).

Detects attendance patterns including frequent absences,
pattern-based absences, missing records, and excessive overtime.
"""

import logging
from collections import Counter
from datetime import timedelta

from django.db.models import Sum, Q
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.hrpayroll.models import Employee, AttendanceRecord, AttendanceTypeCode, EmployeeStateCode

logger = logging.getLogger(__name__)


@register_agent
class AttendanceAnomalyAgent(BaseAgent):
    """Detects attendance anomalies and patterns."""

    AGENT_TYPE = AgentTypeCode.ATTENDANCE_ANOMALY

    def execute(self, *, project_id: str = None, period_days: int = 30, **kwargs) -> list:
        absence_threshold = self.config.get('absence_threshold', 3)
        overtime_weekly_max = self.config.get('overtime_weekly_max', 20)
        pattern_threshold = self.config.get('pattern_threshold', 2)

        now = timezone.now()
        start_date = (now - timedelta(days=period_days)).date()
        end_date = now.date()

        # Get active employees
        employee_filter = Q(statecode=EmployeeStateCode.ACTIVE)
        employees = Employee.objects.filter(employee_filter)

        # Optionally filter by project
        if project_id:
            employee_ids = AttendanceRecord.objects.filter(
                projectid=project_id,
                attendancedate__gte=start_date,
                attendancedate__lte=end_date,
            ).values_list('employeeid', flat=True).distinct()
            employees = employees.filter(employeeid__in=employee_ids)

        results = []

        for emp in employees:
            records = AttendanceRecord.objects.filter(
                employeeid=emp.employeeid,
                attendancedate__gte=start_date,
                attendancedate__lte=end_date,
            ).order_by('attendancedate')

            if project_id:
                records = records.filter(projectid=project_id)

            # 1. Frequent absences (>3 in 30 days)
            absences = records.filter(attendancetype=AttendanceTypeCode.ABSENT)
            absence_count = absences.count()

            if absence_count > absence_threshold:
                result = {
                    'employee_id': str(emp.employeeid),
                    'employee_name': emp.fullname,
                    'anomaly_type': 'frequent_absences',
                    'details': f"{absence_count} absences in {period_days} days",
                    'severity': 'warning' if absence_count <= absence_threshold * 2 else 'critical',
                    'period': f"{start_date} to {end_date}",
                    'recommendation': 'Review attendance pattern and discuss with employee',
                }
                results.append(result)

                self._create_suggestion(
                    title=f"Frequent absences: {emp.fullname} ({absence_count} in {period_days}d)",
                    description=result['details'],
                    confidence=0.9,
                    severity=(
                        SuggestionSeverity.WARNING
                        if absence_count <= absence_threshold * 2
                        else SuggestionSeverity.CRITICAL
                    ),
                    suggested_action='review_attendance',
                    suggested_data=result,
                    relatedentityid=emp.employeeid,
                    relatedentitytype='employee',
                )

            # 2. Pattern absences (same day of week)
            if absence_count >= pattern_threshold:
                weekday_counter = Counter()
                for absence in absences:
                    weekday_counter[absence.attendancedate.strftime('%A')] += 1

                for day_name, count in weekday_counter.items():
                    if count >= pattern_threshold:
                        result = {
                            'employee_id': str(emp.employeeid),
                            'employee_name': emp.fullname,
                            'anomaly_type': 'pattern_absence',
                            'details': f"Absent {count} times on {day_name}",
                            'severity': 'warning',
                            'period': f"{start_date} to {end_date}",
                            'recommendation': f'Investigate recurring {day_name} absences',
                        }
                        results.append(result)

                        self._create_suggestion(
                            title=f"Pattern absence: {emp.fullname} ({day_name})",
                            description=f"Absent {count} times on {day_name} in {period_days} days",
                            confidence=0.75,
                            severity=SuggestionSeverity.WARNING,
                            suggested_action='investigate_pattern',
                            suggested_data=result,
                            relatedentityid=emp.employeeid,
                            relatedentitytype='employee',
                        )

            # 3. Missing records
            record_dates = set(records.values_list('attendancedate', flat=True))
            expected_dates = set()
            current = start_date
            while current <= end_date:
                # Mon-Fri (0-4)
                if current.weekday() < 5:
                    expected_dates.add(current)
                current += timedelta(days=1)

            missing_dates = expected_dates - record_dates
            missing_count = len(missing_dates)

            if missing_count > 3:
                result = {
                    'employee_id': str(emp.employeeid),
                    'employee_name': emp.fullname,
                    'anomaly_type': 'missing_records',
                    'details': f"{missing_count} missing attendance records in {period_days} days",
                    'severity': 'warning',
                    'period': f"{start_date} to {end_date}",
                    'recommendation': 'Verify and complete missing attendance records',
                }
                results.append(result)

                self._create_suggestion(
                    title=f"Missing records: {emp.fullname} ({missing_count} days)",
                    description=result['details'],
                    confidence=0.8,
                    severity=SuggestionSeverity.WARNING,
                    suggested_action='complete_attendance',
                    suggested_data=result,
                    relatedentityid=emp.employeeid,
                    relatedentitytype='employee',
                )

            # 4. Excessive overtime (>20 hrs/week)
            total_overtime = records.aggregate(
                total=Sum('overtimehoursworked')
            )['total'] or 0

            weeks_in_period = max(period_days / 7, 1)
            avg_weekly_overtime = float(total_overtime) / weeks_in_period

            if avg_weekly_overtime > overtime_weekly_max:
                result = {
                    'employee_id': str(emp.employeeid),
                    'employee_name': emp.fullname,
                    'anomaly_type': 'excessive_overtime',
                    'details': (
                        f"Average {avg_weekly_overtime:.1f} overtime hrs/week "
                        f"(threshold: {overtime_weekly_max})"
                    ),
                    'severity': 'warning' if avg_weekly_overtime < overtime_weekly_max * 1.5 else 'critical',
                    'period': f"{start_date} to {end_date}",
                    'recommendation': 'Review workload distribution and staffing levels',
                }
                results.append(result)

                self._create_suggestion(
                    title=f"Excessive overtime: {emp.fullname} ({avg_weekly_overtime:.1f} hrs/wk)",
                    description=result['details'],
                    confidence=0.85,
                    severity=(
                        SuggestionSeverity.WARNING
                        if avg_weekly_overtime < overtime_weekly_max * 1.5
                        else SuggestionSeverity.CRITICAL
                    ),
                    suggested_action='review_overtime',
                    suggested_data=result,
                    relatedentityid=emp.employeeid,
                    relatedentitytype='employee',
                )

        return results
