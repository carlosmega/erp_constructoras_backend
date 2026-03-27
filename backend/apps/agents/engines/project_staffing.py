"""
Project Staffing Agent (Type 15).

Analyzes project staffing to detect over-assignment, under-staffing,
idle employees, and skill gaps across all active projects.
"""

import logging

from django.db.models import Count, Q, Sum

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.projects.models import (
    ConstructionProject,
    ProjectTeamMember,
    ProjectStateCode,
    ProjectRoleCode,
)
from apps.hrpayroll.models import Employee, EmployeeProjectAssignment, EmployeeStateCode, AssignmentStateCode

logger = logging.getLogger(__name__)

# Key roles that every active project should have
REQUIRED_ROLES = [
    ProjectRoleCode.PROJECT_MANAGER,
    ProjectRoleCode.SITE_ENGINEER,
]


@register_agent
class ProjectStaffingAgent(BaseAgent):
    """Analyzes project staffing levels and identifies issues."""

    AGENT_TYPE = AgentTypeCode.PROJECT_STAFFING

    def execute(self, **kwargs) -> dict:
        required_roles = self.config.get('required_roles', [r.value for r in REQUIRED_ROLES])
        max_project_pct = self.config.get('max_assignment_pct', 150)

        active_projects = ConstructionProject.objects.filter(
            statecode=ProjectStateCode.ACTIVE,
        )
        active_employees = Employee.objects.filter(
            statecode=EmployeeStateCode.ACTIVE,
        )

        over_assigned = []
        under_staffed = []
        idle_employees = []
        recommendations = []

        # 1. Over-assigned: employees on multiple projects
        active_assignments = (
            EmployeeProjectAssignment.objects
            .filter(statecode=AssignmentStateCode.ACTIVE)
            .select_related('employeeid', 'projectid')
        )

        employee_assignments = {}
        for assignment in active_assignments:
            emp_id = str(assignment.employeeid_id)
            if emp_id not in employee_assignments:
                employee_assignments[emp_id] = {
                    'employee': assignment.employeeid,
                    'projects': [],
                    'total_hours': 0,
                }
            employee_assignments[emp_id]['projects'].append({
                'project_id': str(assignment.projectid_id),
                'project_name': assignment.projectid.name,
                'role': assignment.role,
                'hours_per_week': float(assignment.hoursperweek or 0),
            })
            employee_assignments[emp_id]['total_hours'] += float(
                assignment.hoursperweek or 0
            )

        for emp_id, data in employee_assignments.items():
            if len(data['projects']) > 1:
                # Assume 48 hrs/week as 100%
                total_pct = round(data['total_hours'] / 48 * 100, 1) if data['total_hours'] > 0 else 0
                if total_pct > max_project_pct or len(data['projects']) > 2:
                    emp = data['employee']
                    entry = {
                        'employee_id': emp_id,
                        'name': emp.fullname,
                        'projects': data['projects'],
                        'total_pct': total_pct,
                    }
                    over_assigned.append(entry)

                    self._create_suggestion(
                        title=f"Over-assigned: {emp.fullname} ({len(data['projects'])} projects, {total_pct}%)",
                        description=(
                            f"Assigned to {len(data['projects'])} projects "
                            f"with total allocation of {total_pct}%"
                        ),
                        confidence=0.85,
                        severity=SuggestionSeverity.WARNING,
                        suggested_action='review_assignment',
                        suggested_data=entry,
                        relatedentityid=emp.employeeid,
                        relatedentitytype='employee',
                    )

        # 2. Under-staffed: projects missing key roles
        for project in active_projects:
            team_roles = set(
                ProjectTeamMember.objects
                .filter(projectid=project.projectid)
                .values_list('role', flat=True)
            )

            missing = [r for r in required_roles if r not in team_roles]
            if missing:
                entry = {
                    'project_id': str(project.projectid),
                    'name': project.name,
                    'missing_roles': missing,
                }
                under_staffed.append(entry)

                self._create_suggestion(
                    title=f"Under-staffed: {project.name} (missing {len(missing)} roles)",
                    description=f"Missing roles: {', '.join(missing)}",
                    confidence=0.9,
                    severity=SuggestionSeverity.WARNING,
                    suggested_action='assign_roles',
                    suggested_data=entry,
                    relatedentityid=project.projectid,
                    relatedentitytype='constructionproject',
                )

        # 3. Idle employees: active without any assignment
        assigned_employee_ids = set(employee_assignments.keys())
        # Also check ProjectTeamMember
        team_member_ids = set(
            str(tm)
            for tm in ProjectTeamMember.objects.filter(
                projectid__statecode=ProjectStateCode.ACTIVE,
            ).values_list('systemuserid', flat=True)
        )

        for emp in active_employees:
            emp_id_str = str(emp.employeeid)
            if emp_id_str not in assigned_employee_ids:
                # Check for last assignment
                last_assignment = (
                    EmployeeProjectAssignment.objects
                    .filter(employeeid=emp.employeeid)
                    .order_by('-startdate')
                    .first()
                )
                entry = {
                    'employee_id': emp_id_str,
                    'name': emp.fullname,
                    'last_assignment': (
                        str(last_assignment.startdate) if last_assignment else None
                    ),
                }
                idle_employees.append(entry)

        if idle_employees:
            self._create_suggestion(
                title=f"{len(idle_employees)} idle employees without project assignment",
                description=(
                    f"Active employees without any project assignment: "
                    + ', '.join(e['name'] for e in idle_employees[:5])
                    + ('...' if len(idle_employees) > 5 else '')
                ),
                confidence=0.8,
                severity=SuggestionSeverity.INFO,
                suggested_action='review_idle_employees',
                suggested_data={'idle_employees': idle_employees},
            )

        # 4. Build recommendations
        if over_assigned:
            recommendations.append(
                f"Review {len(over_assigned)} over-assigned employees to prevent burnout"
            )
        if under_staffed:
            recommendations.append(
                f"Fill {sum(len(p['missing_roles']) for p in under_staffed)} missing "
                f"key roles across {len(under_staffed)} projects"
            )
        if idle_employees:
            recommendations.append(
                f"Consider assigning {len(idle_employees)} idle employees to under-staffed projects"
            )

        return {
            'over_assigned': over_assigned,
            'under_staffed': under_staffed,
            'idle_employees': idle_employees,
            'recommendations': recommendations,
        }
