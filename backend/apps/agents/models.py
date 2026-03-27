"""
Agent models following CDS patterns.

Provides infrastructure for AI-powered agents that analyze data,
generate suggestions, and automate workflows across the ERP system.
"""

import uuid
from django.db import models
from core.models import AuditMixin


# ============================================================================
# Enums
# ============================================================================

class AgentTypeCode(models.IntegerChoices):
    LEAD_SCORING = 1, "Lead Scoring"
    DUPLICATE_DETECTION = 2, "Duplicate Detection"
    EXPENSE_CLASSIFICATION = 3, "Expense Classification"
    BUDGET_ALERT = 4, "Budget Alert"
    PIPELINE_FORECAST = 5, "Pipeline Forecast"
    NEXT_BEST_ACTION = 6, "Next Best Action"
    QUOTE_OPTIMIZATION = 7, "Quote Optimization"
    OPPORTUNITY_STAGE_ADVISOR = 8, "Opportunity Stage Advisor"
    LEAD_QUALIFICATION_ASSISTANT = 9, "Lead Qualification Assistant"
    COST_VARIANCE_ANALYZER = 10, "Cost Variance Analyzer"
    PROVISION_RECONCILIATION = 11, "Provision Reconciliation"
    CLIENT_ESTIMATE_GENERATOR = 12, "Client Estimate Generator"
    PAYROLL_VALIDATION = 13, "Payroll Validation"
    ATTENDANCE_ANOMALY = 14, "Attendance Anomaly"
    PROJECT_STAFFING = 15, "Project Staffing"
    INVOICE_COLLECTION = 16, "Invoice Collection"
    CORPORATE_ALLOCATION = 17, "Corporate Allocation Optimizer"
    CASH_FLOW_PROJECTOR = 18, "Cash Flow Projector"
    ACTIVITY_SUMMARIZER = 19, "Activity Summarizer"
    EMAIL_CRM_LINKER = 20, "Email-to-CRM Linker"
    MEETING_PREP = 21, "Meeting Prep"
    DATA_QUALITY = 22, "Data Quality"
    AUDIT_COMPLIANCE = 23, "Audit Compliance"
    PERMISSION_ANOMALY = 24, "Permission Anomaly"
    PROYECCION_ESTIMATOR = 25, "Proyección Cost Estimator"
    BID_ANALYSIS = 26, "Bid Analysis"
    SMART_NOTIFICATION = 27, "Smart Notification Router"
    ESCALATION = 28, "Escalation"
    INVOICE_INBOX_PROCESSOR = 29, "Invoice Inbox Processor"


class AgentStatusCode(models.IntegerChoices):
    PENDING = 0, "Pending"
    RUNNING = 1, "Running"
    COMPLETED = 2, "Completed"
    FAILED = 3, "Failed"
    CANCELLED = 4, "Cancelled"


class SuggestionStatusCode(models.IntegerChoices):
    PENDING = 0, "Pending"
    ACCEPTED = 1, "Accepted"
    REJECTED = 2, "Rejected"
    EXPIRED = 3, "Expired"


class SuggestionSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"
    EXCEEDED = "exceeded", "Exceeded"


# ============================================================================
# Models
# ============================================================================

class AgentConfig(AuditMixin):
    """Per-agent configuration with optional project scope."""

    agentconfigid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='agentconfigid'
    )
    agenttype = models.IntegerField(
        choices=AgentTypeCode.choices, db_column='agenttype'
    )
    enabled = models.BooleanField(default=True, db_column='enabled')
    config = models.JSONField(
        default=dict, db_column='config',
        help_text="Agent-specific configuration (thresholds, weights, rules)"
    )
    schedule_cron = models.CharField(
        max_length=50, blank=True, default='', db_column='schedulecron',
        help_text="Cron expression for scheduled runs. Empty = on-demand only."
    )
    projectid = models.UUIDField(
        null=True, blank=True, db_column='projectid',
        help_text="Scope to a specific project (null = global)"
    )
    ownerid = models.ForeignKey(
        'users.SystemUser', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='ownerid', related_name='agent_configs'
    )

    class Meta:
        db_table = 'agentconfig'
        unique_together = ('agenttype', 'projectid')
        ordering = ['agenttype']

    def __str__(self):
        return f"AgentConfig({self.get_agenttype_display()}, project={self.projectid})"


class AgentRun(AuditMixin):
    """Record of each agent execution."""

    agentrunid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='agentrunid'
    )
    agenttype = models.IntegerField(
        choices=AgentTypeCode.choices, db_column='agenttype'
    )
    statecode = models.IntegerField(
        choices=AgentStatusCode.choices,
        default=AgentStatusCode.PENDING, db_column='statecode'
    )
    input_params = models.JSONField(
        default=dict, db_column='inputparams'
    )
    output_summary = models.JSONField(
        default=dict, db_column='outputsummary'
    )
    suggestions_count = models.IntegerField(default=0, db_column='suggestionscount')
    accepted_count = models.IntegerField(default=0, db_column='acceptedcount')
    rejected_count = models.IntegerField(default=0, db_column='rejectedcount')
    duration_ms = models.IntegerField(null=True, blank=True, db_column='durationms')
    error_message = models.TextField(blank=True, default='', db_column='errormessage')
    triggered_by = models.CharField(
        max_length=20, default='manual', db_column='triggeredby',
        help_text="manual | schedule | event"
    )

    class Meta:
        db_table = 'agentrun'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['agenttype', '-createdon']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return f"AgentRun({self.get_agenttype_display()}, {self.get_statecode_display()})"


class AgentSuggestion(AuditMixin):
    """Individual suggestion generated by an agent run."""

    suggestionid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='suggestionid'
    )
    agentrun = models.ForeignKey(
        AgentRun, on_delete=models.CASCADE,
        related_name='suggestions', db_column='agentrunid'
    )
    agenttype = models.IntegerField(
        choices=AgentTypeCode.choices, db_column='agenttype'
    )
    statecode = models.IntegerField(
        choices=SuggestionStatusCode.choices,
        default=SuggestionStatusCode.PENDING, db_column='statecode'
    )

    # Polymorphic related entity (same pattern as Notification)
    relatedentityid = models.UUIDField(
        null=True, blank=True, db_column='relatedentityid'
    )
    relatedentitytype = models.CharField(
        max_length=50, blank=True, default='', db_column='relatedentitytype'
    )

    # Content
    title = models.CharField(max_length=255, db_column='title')
    description = models.TextField(blank=True, default='', db_column='description')
    confidence = models.FloatField(
        default=0.0, db_column='confidence',
        help_text="Confidence score 0.0 - 1.0"
    )
    severity = models.CharField(
        max_length=20, choices=SuggestionSeverity.choices,
        default=SuggestionSeverity.INFO, db_column='severity'
    )

    # Suggested action
    suggested_action = models.CharField(
        max_length=100, blank=True, default='', db_column='suggestedaction'
    )
    suggested_data = models.JSONField(
        default=dict, db_column='suggesteddata'
    )

    # Resolution
    resolved_by = models.ForeignKey(
        'users.SystemUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_suggestions', db_column='resolvedby'
    )
    resolved_on = models.DateTimeField(
        null=True, blank=True, db_column='resolvedon'
    )
    resolution_notes = models.TextField(
        blank=True, default='', db_column='resolutionnotes'
    )

    class Meta:
        db_table = 'agentsuggestion'
        ordering = ['-confidence', '-createdon']
        indexes = [
            models.Index(fields=['agenttype', 'statecode']),
            models.Index(fields=['relatedentitytype', 'relatedentityid']),
            models.Index(fields=['agentrun', '-confidence']),
        ]

    def __str__(self):
        return f"Suggestion({self.title[:50]}, confidence={self.confidence:.2f})"
