"""
Agent engines package.

Import all engines to trigger @register_agent decorator registration.
"""

from apps.agents.engines.lead_scoring import LeadScoringAgent  # noqa: F401
from apps.agents.engines.duplicate_detection import DuplicateDetectionAgent  # noqa: F401
from apps.agents.engines.expense_classification import ExpenseClassificationAgent  # noqa: F401
from apps.agents.engines.budget_alert import BudgetAlertAgent  # noqa: F401
from apps.agents.engines.pipeline_forecast import PipelineForecastAgent  # noqa: F401
from apps.agents.engines.next_best_action import NextBestActionAgent  # noqa: F401
from apps.agents.engines.quote_optimization import QuoteOptimizationAgent  # noqa: F401
from apps.agents.engines.opportunity_stage_advisor import OpportunityStageAdvisorAgent  # noqa: F401
from apps.agents.engines.lead_qualification_assistant import LeadQualificationAssistantAgent  # noqa: F401
from apps.agents.engines.cost_variance_analyzer import CostVarianceAnalyzerAgent  # noqa: F401
from apps.agents.engines.provision_reconciliation import ProvisionReconciliationAgent  # noqa: F401
from apps.agents.engines.client_estimate_generator import ClientEstimateGeneratorAgent  # noqa: F401
from apps.agents.engines.payroll_validation import PayrollValidationAgent  # noqa: F401
from apps.agents.engines.attendance_anomaly import AttendanceAnomalyAgent  # noqa: F401
from apps.agents.engines.project_staffing import ProjectStaffingAgent  # noqa: F401
from apps.agents.engines.invoice_collection import InvoiceCollectionAgent  # noqa: F401
from apps.agents.engines.corporate_allocation_optimizer import CorporateAllocationOptimizerAgent  # noqa: F401
from apps.agents.engines.cash_flow_projector import CashFlowProjectorAgent  # noqa: F401
from apps.agents.engines.activity_summarizer import ActivitySummarizerAgent  # noqa: F401
from apps.agents.engines.email_crm_linker import EmailCrmLinkerAgent  # noqa: F401
from apps.agents.engines.meeting_prep import MeetingPrepAgent  # noqa: F401
from apps.agents.engines.data_quality import DataQualityAgent  # noqa: F401
from apps.agents.engines.audit_compliance import AuditComplianceAgent  # noqa: F401
from apps.agents.engines.permission_anomaly import PermissionAnomalyAgent  # noqa: F401
from apps.agents.engines.proyeccion_estimator import ProyeccionEstimatorAgent  # noqa: F401
from apps.agents.engines.bid_analysis import BidAnalysisAgent  # noqa: F401
from apps.agents.engines.smart_notification import SmartNotificationAgent  # noqa: F401
from apps.agents.engines.escalation import EscalationAgent  # noqa: F401
from apps.agents.engines.invoice_inbox_processor import InvoiceInboxProcessorAgent  # noqa: F401
