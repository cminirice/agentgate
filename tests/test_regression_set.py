from datetime import UTC, datetime

import pytest

from agentgate.case import DatasetService
from agentgate.domain import (
    Case,
    CaseProvenance,
    CaseTurn,
    Dataset,
    DatasetPurpose,
    DatasetVersion,
    DatasetVersionStatus,
)
from agentgate.domain.base import content_sha256
from agentgate.storage.sqlite import SQLiteRepository


def old_case_payload() -> dict:
    return {
        "id": "old-case",
        "name": "Old case",
        "turns": [{"id": "old-turn", "input": {"message": "hello"}}],
    }


def test_old_dataset_and_case_payloads_default_to_standard_without_provenance():
    dataset = Dataset.model_validate({"id": "d", "name": "old"})
    case = Case.model_validate(old_case_payload())

    assert dataset.purpose == DatasetPurpose.STANDARD
    assert case.provenance is None


def test_regression_case_provenance_is_hashed_but_none_keeps_old_hash():
    old_case = Case.model_validate(old_case_payload())
    old_payload = {
        "dataset_id": "dataset",
        "cases": [old_case.model_dump(mode="json", exclude={"provenance"})],
        "notes": "",
    }
    old_version_payload = {
        "dataset_id": "dataset",
        "status": DatasetVersionStatus.PUBLISHED,
        "version": 1,
        "published_at": datetime(2026, 8, 20, tzinfo=UTC),
        "cases": old_payload["cases"],
        "notes": "",
        "content_sha256": content_sha256(old_payload),
    }
    restored = DatasetVersion.model_validate(old_version_payload)

    sourced = old_case.model_copy(update={
        "provenance": CaseProvenance(
            source_run_id="run-1",
            source_dataset_id="source-dataset",
            source_dataset_version=3,
            source_case_id=old_case.id,
            captured_at=datetime(2026, 8, 20, tzinfo=UTC),
            reason="high risk",
        ),
    })
    sourced_version = DatasetVersion(
        dataset_id="dataset",
        status=DatasetVersionStatus.PUBLISHED,
        version=1,
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
        cases=(sourced,),
    )

    assert restored.content_sha256 == old_version_payload["content_sha256"]
    assert sourced_version.content_sha256 != restored.content_sha256


def test_case_provenance_is_immutable():
    provenance = CaseProvenance(
        source_run_id="run-1",
        source_dataset_id="dataset-1",
        source_dataset_version=1,
        source_case_id="case-1",
        captured_at=datetime(2026, 8, 20, tzinfo=UTC),
    )

    with pytest.raises((TypeError, ValueError)):
        provenance.reason = "changed"


def test_dataset_creation_accepts_regression_purpose_and_copy_preserves_it(tmp_path):
    service = DatasetService(SQLiteRepository(tmp_path / "regression.db"))
    source = service.create_dataset("Source", purpose=DatasetPurpose.REGRESSION)
    service.create_draft(source.id)
    source_case = Case(
        id="source-case",
        name="Source case",
        turns=(CaseTurn(id="source-turn", input={"message": "hello"}),),
        provenance=CaseProvenance(
            source_run_id="run-1",
            source_dataset_id="source-dataset",
            source_dataset_version=1,
            source_case_id="original-case",
            captured_at=datetime(2026, 8, 20, tzinfo=UTC),
        ),
    )
    service.save_case(source.id, source_case)
    service.publish_draft(source.id)

    copied, draft = service.copy_dataset(source.id, "Copied")

    assert copied.purpose == DatasetPurpose.REGRESSION
    assert draft.cases[0].provenance == source_case.provenance
