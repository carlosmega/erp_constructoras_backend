"""
Router tests for HR & Payroll API endpoints.

Tests CRUD endpoints for employees, payroll runs, attendance,
and permission checks for different user roles.
"""

import uuid
import pytest
from decimal import Decimal
from datetime import date

from apps.hrpayroll.models import (
    PayrollRunStateCode, PeriodStateCode, EmployeeStatusCode,
)
from apps.hrpayroll.tests.factories import (
    EmployeeFactory, PayrollPeriodFactory, PayrollRunFactory,
    PayrollEntryFactory, AttendanceRecordFactory,
    DeductionTypeFactory, AdditionTypeFactory,
)


# ============================================================================
# Employees Router Tests
# ============================================================================

@pytest.mark.contract
class TestListEmployees:
    def test_returns_200(self, admin_auth_client, system_admin):
        EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/employees/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_filter_by_statecode(self, admin_auth_client, system_admin):
        EmployeeFactory(statecode=0, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/employees/?statecode=0')
        assert response.status_code == 200
        data = response.json()
        assert all(item['statecode'] == 0 for item in data)

    def test_salesperson_can_read_employees(self, auth_client, salesperson):
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/employees/')
        assert response.status_code == 200

    def test_readonly_can_read_employees(self, readonly_auth_client, readonly_user):
        response = readonly_auth_client.get('/api/employees/')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/employees/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateEmployee:
    def test_creates_employee(self, admin_auth_client, system_admin):
        payload = {
            'firstname': 'Juan',
            'lastname': 'Perez',
            'hiredate': '2026-01-15',
            'position': 'Obrero General',
            'department': 'Obra Civil',
            'basesalary': '3500.00',
        }
        response = admin_auth_client.post(
            '/api/employees/', payload, content_type='application/json',
        )
        assert response.status_code == 201
        data = response.json()
        assert data['firstname'] == 'Juan'
        assert data['lastname'] == 'Perez'
        assert data['fullname'] == 'Juan Perez'
        assert 'EMP-' in data['employeenumber']

    def test_readonly_denied(self, readonly_auth_client):
        payload = {
            'firstname': 'Blocked', 'lastname': 'User',
            'hiredate': '2026-01-01', 'position': 'X', 'department': 'X',
            'basesalary': '1000.00',
        }
        response = readonly_auth_client.post(
            '/api/employees/', payload, content_type='application/json',
        )
        assert response.status_code == 403

    def test_salesperson_denied_create(self, auth_client):
        """Salesperson only has EMPLOYEE_READ, not EMPLOYEE_CREATE."""
        payload = {
            'firstname': 'Blocked', 'lastname': 'User',
            'hiredate': '2026-01-01', 'position': 'X', 'department': 'X',
            'basesalary': '1000.00',
        }
        response = auth_client.post(
            '/api/employees/', payload, content_type='application/json',
        )
        assert response.status_code == 403


@pytest.mark.contract
class TestGetEmployee:
    def test_returns_employee(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/employees/{emp.employeeid}')
        assert response.status_code == 200
        assert response.json()['employeeid'] == str(emp.employeeid)

    def test_not_found(self, admin_auth_client):
        response = admin_auth_client.get(f'/api/employees/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateEmployee:
    def test_updates_employee(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/employees/{emp.employeeid}',
            {'position': 'Ingeniero Senior'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['position'] == 'Ingeniero Senior'


@pytest.mark.contract
class TestTerminateEmployee:
    def test_terminates_employee(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(
            f'/api/employees/{emp.employeeid}/terminate',
            {'terminationdate': '2026-03-26', 'statuscode': EmployeeStatusCode.VOLUNTARY_EXIT},
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['statecode'] == 2  # TERMINATED


@pytest.mark.contract
class TestDeleteEmployee:
    def test_deletes_employee(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/employees/{emp.employeeid}')
        assert response.status_code == 204


# ============================================================================
# Payroll Runs Router Tests
# ============================================================================

@pytest.mark.contract
class TestListPayrollRuns:
    def test_returns_200(self, admin_auth_client, system_admin):
        PayrollRunFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/payroll-runs/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_salesperson_can_read(self, auth_client, salesperson):
        response = auth_client.get('/api/payroll-runs/')
        assert response.status_code == 200


@pytest.mark.contract
class TestCreatePayrollRun:
    def test_creates_run(self, admin_auth_client, system_admin, salesperson):
        period = PayrollPeriodFactory(createdby=system_admin, modifiedby=system_admin)
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {'payrollperiodid': str(period.payrollperiodid)}
        response = admin_auth_client.post(
            '/api/payroll-runs/', payload, content_type='application/json',
        )
        assert response.status_code == 201
        data = response.json()
        assert 'NOM-' in data['runnumber']

    def test_salesperson_denied_create(self, auth_client, salesperson):
        """Salesperson has PAYROLL_READ only, not PAYROLL_CREATE."""
        period = PayrollPeriodFactory(createdby=salesperson, modifiedby=salesperson)
        payload = {'payrollperiodid': str(period.payrollperiodid)}
        response = auth_client.post(
            '/api/payroll-runs/', payload, content_type='application/json',
        )
        assert response.status_code == 403


@pytest.mark.contract
class TestGetPayrollRun:
    def test_returns_run(self, admin_auth_client, system_admin):
        run = PayrollRunFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get(f'/api/payroll-runs/{run.payrollrunid}')
        assert response.status_code == 200
        assert response.json()['payrollrunid'] == str(run.payrollrunid)


@pytest.mark.contract
class TestPayrollRunWorkflowEndpoints:
    def test_submit_run(self, admin_auth_client, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.CALCULATED,
            employeecount=3,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.post(f'/api/payroll-runs/{run.payrollrunid}/submit')
        assert response.status_code == 200
        assert response.json()['statecode'] == PayrollRunStateCode.PENDING_APPROVAL

    def test_approve_run(self, admin_auth_client, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.PENDING_APPROVAL,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.post(f'/api/payroll-runs/{run.payrollrunid}/approve')
        assert response.status_code == 200
        assert response.json()['statecode'] == PayrollRunStateCode.APPROVED

    def test_reject_run(self, admin_auth_client, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.PENDING_APPROVAL,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.post(
            f'/api/payroll-runs/{run.payrollrunid}/reject',
            {'reason': 'Amounts incorrect'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['statecode'] == PayrollRunStateCode.REJECTED

    def test_mark_paid(self, admin_auth_client, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.APPROVED,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.post(f'/api/payroll-runs/{run.payrollrunid}/mark-paid')
        assert response.status_code == 200
        assert response.json()['statecode'] == PayrollRunStateCode.PAID


# ============================================================================
# Attendance Router Tests
# ============================================================================

@pytest.mark.contract
class TestListAttendance:
    def test_returns_200(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 25),
            createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.get('/api/attendance/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_salesperson_can_read(self, auth_client, salesperson):
        response = auth_client.get('/api/attendance/')
        assert response.status_code == 200


@pytest.mark.contract
class TestCreateAttendance:
    def test_creates_attendance(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        payload = {
            'employeeid': str(emp.employeeid),
            'attendancedate': '2026-03-25',
            'regularhoursworked': '8.00',
            'attendancetype': 0,
        }
        response = admin_auth_client.post(
            '/api/attendance/', payload, content_type='application/json',
        )
        assert response.status_code == 201
        data = response.json()
        assert data['employeeid'] == str(emp.employeeid)

    def test_salesperson_can_create_attendance(self, auth_client, salesperson):
        """Salesperson has ATTENDANCE_CREATE permission."""
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'employeeid': str(emp.employeeid),
            'attendancedate': '2026-03-25',
        }
        response = auth_client.post(
            '/api/attendance/', payload, content_type='application/json',
        )
        assert response.status_code == 201

    def test_readonly_denied(self, readonly_auth_client, readonly_user):
        payload = {
            'employeeid': str(uuid.uuid4()),
            'attendancedate': '2026-03-25',
        }
        response = readonly_auth_client.post(
            '/api/attendance/', payload, content_type='application/json',
        )
        assert response.status_code == 403


@pytest.mark.contract
class TestDeleteAttendance:
    def test_admin_can_delete(self, admin_auth_client, system_admin):
        emp = EmployeeFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        record = AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 24),
            createdby=system_admin, modifiedby=system_admin,
        )
        response = admin_auth_client.delete(f'/api/attendance/{record.attendanceid}')
        assert response.status_code == 204

    def test_salesperson_denied_delete(self, auth_client, salesperson):
        """Salesperson does not have ATTENDANCE_DELETE permission."""
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        record = AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 24),
            createdby=salesperson, modifiedby=salesperson,
        )
        response = auth_client.delete(f'/api/attendance/{record.attendanceid}')
        assert response.status_code == 403


# ============================================================================
# Catalog Router Tests (Deduction/Addition Types)
# ============================================================================

@pytest.mark.contract
class TestDeductionTypeRouter:
    def test_list_deduction_types(self, admin_auth_client, system_admin):
        DeductionTypeFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/deduction-types/')
        assert response.status_code == 200

    def test_create_deduction_type(self, admin_auth_client, system_admin):
        payload = {
            'code': 'TEST01',
            'name': 'Test Deduction',
            'calculationtype': 0,
            'defaultvalue': '100.0000',
            'isstatutory': False,
        }
        response = admin_auth_client.post(
            '/api/deduction-types/', payload, content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['code'] == 'TEST01'

    def test_salesperson_denied_create_catalog(self, auth_client):
        """Salesperson does not have HR_CATALOG_MANAGE permission."""
        payload = {'code': 'X', 'name': 'X'}
        response = auth_client.post(
            '/api/deduction-types/', payload, content_type='application/json',
        )
        assert response.status_code == 403


@pytest.mark.contract
class TestAdditionTypeRouter:
    def test_list_addition_types(self, admin_auth_client, system_admin):
        AdditionTypeFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.get('/api/addition-types/')
        assert response.status_code == 200

    def test_create_addition_type(self, admin_auth_client, system_admin):
        payload = {
            'code': 'TESTADD',
            'name': 'Test Addition',
            'calculationtype': 0,
            'defaultvalue': '250.0000',
            'istaxable': True,
        }
        response = admin_auth_client.post(
            '/api/addition-types/', payload, content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['code'] == 'TESTADD'
