"""Tests for the race-safe auto-numbering helpers (core.numbering)."""

from types import SimpleNamespace

import pytest
from django.db import IntegrityError

from core.numbering import next_numbered_code, create_with_retry
from apps.proyeccion.models import EstimationProject
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.django_db
class TestNextNumberedCode:
    def test_empty_starts_at_one(self):
        assert (
            next_numbered_code(EstimationProject, "estimationnumber", "EST-2026-", width=3)
            == "EST-2026-001"
        )

    def test_increments_from_max(self):
        EstimationProjectFactory(estimationnumber="EST-2026-001")
        EstimationProjectFactory(estimationnumber="EST-2026-002")
        assert (
            next_numbered_code(EstimationProject, "estimationnumber", "EST-2026-", width=3)
            == "EST-2026-003"
        )

    def test_robust_to_deletion(self):
        # A count()-based scheme would re-issue a freed number and collide with an
        # existing higher one; the max-suffix scheme does not.
        EstimationProjectFactory(estimationnumber="EST-2026-001")
        p2 = EstimationProjectFactory(estimationnumber="EST-2026-002")
        EstimationProjectFactory(estimationnumber="EST-2026-003")
        p2.delete()  # 001 and 003 remain; count() == 2 would yield 003 (collision)
        assert (
            next_numbered_code(EstimationProject, "estimationnumber", "EST-2026-", width=3)
            == "EST-2026-004"
        )

    def test_prefixes_are_isolated(self):
        EstimationProjectFactory(estimationnumber="EST-2025-099")
        assert (
            next_numbered_code(EstimationProject, "estimationnumber", "EST-2026-", width=3)
            == "EST-2026-001"
        )


@pytest.mark.django_db
class TestCreateWithRetry:
    def test_succeeds_first_try(self):
        assert create_with_retry(lambda: "ok") == "ok"

    def test_retries_on_integrity_error_then_succeeds(self):
        calls = {"n": 0}

        def op():
            calls["n"] += 1
            if calls["n"] < 3:
                raise IntegrityError("duplicate key")
            return calls["n"]

        assert create_with_retry(op, max_retries=5) == 3
        assert calls["n"] == 3

    def test_exhausts_retries_and_reraises(self):
        def op():
            raise IntegrityError("always collides")

        with pytest.raises(IntegrityError):
            create_with_retry(op, max_retries=3)


@pytest.mark.django_db
class TestEstimationServiceRaceSafe:
    """The estimation service survives a concurrent number collision via retry."""

    def test_create_project_retries_past_a_collision(self, salesperson, mocker):
        from apps.proyeccion import services

        # A row already owns EST-2026-001; the first generated number collides.
        EstimationProjectFactory(estimationnumber="EST-2026-001", ownerid=salesperson)

        # Force the first generation to collide, then return the next free value.
        seq = iter(["EST-2026-001", "EST-2026-002"])
        mocker.patch.object(
            services, "next_numbered_code", side_effect=lambda *a, **k: next(seq)
        )

        dto = SimpleNamespace(
            name="Race test", description=None, accountid=None, opportunityid=None,
            presentationdate=None, estimatedstartdate=None, estimatedenddate=None,
            durationmonths=None, projecttype=None, biddingtype=None, periodtype=None,
            estimatedcontractamount=None, exchangerate_mxn_usd=None,
        )

        project = services.EstimationProjectService.create_project(dto, salesperson)

        # Retried past the duplicate to the next free number instead of erroring.
        assert project.estimationnumber == "EST-2026-002"
        assert EstimationProject.objects.filter(estimationnumber="EST-2026-002").count() == 1
