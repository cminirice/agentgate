# Regression-set Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users copy a Case from a completed RunSnapshot into a versioned regression Dataset and execute it through the existing evaluation workflow.

**Architecture:** Extend Dataset with a backward-compatible purpose and Case with optional provenance. Reuse Dataset drafts, publishing, RunEngine, reports, and Trace; add one atomic repository operation and one control-plane command for adding a snapshotted Case to a new or existing regression Dataset.

**Tech Stack:** Python 3.14, Pydantic, SQLite, FastAPI, Vue 3, TypeScript, Element Plus, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-20-regression-set-design.md`

## Global Constraints

- Regression sets are Datasets and never persist Evaluator, MetricPlan, or GateSpec configuration.
- Source Case content comes only from a completed RunSnapshot.
- A source Case may appear at most once per regression Dataset, keyed by `source_case_id`.
- Existing Dataset, Case, DatasetVersion, and snapshot hashes remain readable.
- The first increment does not implement whole-Run comparison or a Result Center.
- `docs/dataset/generation-plan.md` is unrelated user work and must not be staged.

---

### Task 1: Backward-compatible Dataset purpose and Case provenance

**Files:**
- Modify: `src/agentgate/domain/case.py`
- Modify: `src/agentgate/domain/__init__.py`
- Modify: `src/agentgate/case/service.py`
- Test: `tests/test_regression_set.py`
- Test: `tests/test_snapshot_immutability.py`

**Interfaces:**
- Produces: `DatasetPurpose`, `CaseProvenance`, `Dataset.purpose`, `Case.provenance`.
- Produces: `DatasetService.create_dataset(name, description="", purpose=DatasetPurpose.STANDARD)`.
- Preserves: hashes created before `Case.provenance` existed.

- [ ] **Step 1: Write failing compatibility and model tests**

```python
def test_old_dataset_and_case_payloads_default_to_standard_without_provenance():
    dataset = Dataset.model_validate({"id": "d", "name": "old"})
    case = Case.model_validate(old_case_payload())
    assert dataset.purpose == DatasetPurpose.STANDARD
    assert case.provenance is None


def test_regression_case_provenance_is_hashed_but_none_keeps_old_hash():
    old = published_version_payload_without_provenance()
    assert DatasetVersion.model_validate(old).content_sha256 == old["content_sha256"]
    sourced = DatasetVersion.model_validate(version_payload_with_provenance())
    assert sourced.content_sha256 != old["content_sha256"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set.py tests/test_snapshot_immutability.py -q`

Expected: import/model failures for the new types and fields.

- [ ] **Step 3: Implement enums, provenance, defaults, and compatible hashing**

Add `DatasetPurpose(StrEnum)` with `STANDARD` and `REGRESSION`. Add frozen Pydantic-compatible `CaseProvenance` fields exactly as specified. In `DatasetVersion.validate_version_and_hash`, serialize each Case and remove `provenance` only when it is `None` before calling `content_sha256`.

Extend `DatasetService.create_dataset`:

```python
def create_dataset(
    self,
    name: str,
    description: str = "",
    purpose: DatasetPurpose = DatasetPurpose.STANDARD,
) -> Dataset:
    if not name.strip():
        raise ValueError("dataset name is required")
    dataset = Dataset(
        name=name.strip(),
        description=description.strip(),
        purpose=purpose,
    )
    self.repository.save_dataset(dataset)
    return dataset
```

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set.py tests/test_snapshot_immutability.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agentgate/domain/case.py src/agentgate/domain/__init__.py src/agentgate/case/service.py tests/test_regression_set.py tests/test_snapshot_immutability.py
git commit -m "feat: add regression dataset contracts"
```

### Task 2: Atomic new regression Dataset persistence

**Files:**
- Modify: `src/agentgate/storage/base.py`
- Modify: `src/agentgate/storage/sqlite.py`
- Test: `tests/test_regression_set.py`

**Interfaces:**
- Consumes: `Dataset`, draft `DatasetVersion`.
- Produces: `AgentGateRepository.save_dataset_with_draft(dataset, draft) -> None`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_save_dataset_with_draft_persists_both(tmp_path):
    repo = SQLiteRepository(tmp_path / "atomic.db")
    dataset, draft = regression_dataset_and_draft()
    repo.save_dataset_with_draft(dataset, draft)
    assert repo.get_dataset(dataset.id) == dataset
    assert repo.get_dataset_draft(dataset.id) == draft


def test_save_dataset_with_draft_rolls_back_on_invalid_duplicate(tmp_path):
    repo = SQLiteRepository(tmp_path / "rollback.db")
    dataset, draft = regression_dataset_and_draft()
    repo.save_dataset(dataset)
    with pytest.raises(Exception):
        repo.save_dataset_with_draft(dataset, draft)
    assert repo.get_dataset_draft(dataset.id) is None
```

- [ ] **Step 2: Run the repository tests and verify failure**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set.py -k save_dataset_with_draft -q`

- [ ] **Step 3: Implement a single SQLite transaction**

Add the protocol method. In SQLite, validate `draft.dataset_id == dataset.id` and `draft.status == DRAFT`, then insert the Dataset and draft rows inside the same `with self._connect() as db` transaction. Do not call the two public save methods because each opens its own connection.

- [ ] **Step 4: Run focused tests and commit**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set.py -k save_dataset_with_draft -q`

```bash
git add src/agentgate/storage/base.py src/agentgate/storage/sqlite.py tests/test_regression_set.py
git commit -m "feat: persist regression dataset drafts atomically"
```

### Task 3: Regression membership application service

**Files:**
- Modify: `src/agentgate/control_plane/service.py`
- Modify: `src/agentgate/case/service.py`
- Test: `tests/test_regression_set.py`

**Interfaces:**
- Produces: `EvaluationService.add_case_to_regression_dataset(*, run_id: str, case_id: str, regression_dataset_id: str | None, new_dataset_name: str | None, new_dataset_description: str = "", reason: str = "") -> tuple[Dataset, DatasetVersion, Case]`.
- Consumes: completed `Run`, source `RunSnapshot.dataset`, DatasetService, repository atomic creation.

- [ ] **Step 1: Write failing service behavior tests**

Cover new target, existing target with active draft, existing published target without draft, exact snapshot copy, new internal Case ID, complete provenance, duplicate rejection across Runs, same source allowed in a different regression Dataset, same content allowed for different source IDs, and no partial writes on every validation error.

Representative assertion:

```python
dataset, draft, copied = service.add_case_to_regression_dataset(
    run_id=run.id,
    case_id=source.id,
    regression_dataset_id=None,
    new_dataset_name="Loan regressions",
    reason="direct approval",
)
assert dataset.purpose == DatasetPurpose.REGRESSION
assert copied.id != source.id
assert copied.model_copy(update={"id": source.id, "provenance": None}) == source
assert copied.provenance.source_run_id == run.id
assert copied.provenance.source_case_id == source.id
```

- [ ] **Step 2: Run tests and verify failure**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set.py -k 'add_case or duplicate or completed' -q`

- [ ] **Step 3: Implement validation and draft composition**

Use keyword-only arguments from the spec. Require exactly one target mode. Resolve the source from `run.snapshot.dataset.cases`. Reject non-completed Runs, archived/standard targets, and any effective draft Case whose `provenance.source_case_id` matches. Create a fresh copied Case ID and `captured_at=utcnow()`.

For an existing target without a draft, build the next draft from the latest published version before appending. For new target mode, construct Dataset and draft in memory, validate fully, then call `save_dataset_with_draft` once.

- [ ] **Step 4: Run service tests and commit**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set.py -q`

```bash
git add src/agentgate/control_plane/service.py src/agentgate/case/service.py tests/test_regression_set.py
git commit -m "feat: add cases to regression datasets"
```

### Task 4: HTTP API and JSON compatibility

**Files:**
- Modify: `src/agentgate/server/application.py`
- Modify: `src/agentgate/case/import_export.py`
- Test: `tests/test_regression_set_api.py`
- Test: `tests/test_dataset_import_export.py`

**Interfaces:**
- Produces: `POST /api/runs/{run_id}/cases/{case_id}/regression`.
- Extends: `POST /api/datasets` body with `purpose`, default `standard`.
- Preserves: JSON import/export round trips for old and new payloads.

- [ ] **Step 1: Write failing API tests**

Test existing and new target requests, response `{dataset, draft, case}`, 404 for unknown Run/Case/Dataset, 422 for invalid target mode/non-completed Run/standard or archived target/duplicate, and `purpose` in list/detail responses.

- [ ] **Step 2: Run API tests and verify failure**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set_api.py tests/test_dataset_import_export.py -q`

- [ ] **Step 3: Implement request models and endpoint**

```python
class AddRegressionCaseRequest(BaseModel):
    regression_dataset_id: str | None = None
    new_dataset_name: str | None = None
    new_dataset_description: str = ""
    reason: str = ""
```

Map lookup failures to 404 and validation failures to 422. Extend `CreateDatasetRequest` with `purpose: DatasetPurpose = DatasetPurpose.STANDARD` and pass it to DatasetService.

- [ ] **Step 4: Verify JSON round trips and commit**

Run: `PYTHONPATH=src python3 -m pytest tests/test_regression_set_api.py tests/test_dataset_import_export.py -q`

```bash
git add src/agentgate/server/application.py src/agentgate/case/import_export.py tests/test_regression_set_api.py tests/test_dataset_import_export.py
git commit -m "feat: expose regression dataset workflow API"
```

### Task 5: Web types and API client

**Files:**
- Modify: `web/src/types/dataset.ts`
- Modify: `web/src/api/datasets.ts`
- Modify: `web/src/api/client.ts`

**Interfaces:**
- Produces: TypeScript `DatasetPurpose`, `CaseProvenance`, extended records.
- Produces: `api.addCaseToRegressionDataset(runId, caseId, request)`.
- Extends: `datasetApi.create(name, description, purpose)`.

- [ ] **Step 1: Add TypeScript contracts matching server JSON**

```typescript
export type DatasetPurpose = 'standard' | 'regression'
export interface CaseProvenance {
  source_type: 'run_result'
  source_run_id: string
  source_dataset_id: string
  source_dataset_version: number
  source_case_id: string
  captured_at: string
  reason: string
}
```

- [ ] **Step 2: Add request and response APIs**

Define a discriminated UI request shape that serializes to the backend body, encode path IDs, and type the response as `{dataset: DatasetRecord; draft: DatasetVersion; case: EvaluationCase}`.

- [ ] **Step 3: Run typecheck and commit**

Run: `cd web && npm run typecheck`

```bash
git add web/src/types/dataset.ts web/src/api/datasets.ts web/src/api/client.ts
git commit -m "feat: add regression workflow web contracts"
```

### Task 6: Result-page add dialog and Dataset badges/provenance

**Files:**
- Modify: `web/src/App.vue`
- Modify: `web/src/pages/DatasetWorkspace.vue`
- Modify: `web/src/components/dataset/DatasetList.vue`
- Modify: `web/src/components/dataset/CaseEditor.vue`
- Modify: `web/src/style.css`
- Test: `web/tests/demo.spec.ts`
- Test: `web/tests/dataset.spec.ts`

**Interfaces:**
- Consumes: API and types from Task 5.
- Produces: one `加入回归集` action per completed-Run Case group.
- Produces: existing/new target dialog, success handoff, Dataset badge, read-only provenance.

- [ ] **Step 1: Write failing Playwright scenarios**

Add desktop/mobile scenarios that launch the risky Agent, add its Case to a new regression Dataset with a reason, keep the original report visible, open the new draft, verify badge/provenance, reject a duplicate from a later Run, publish the draft, and launch the published regression Dataset through the normal evaluation form.

- [ ] **Step 2: Run the focused browser tests and verify failure**

Run: `cd web && npm run test:e2e -- demo.spec.ts dataset.spec.ts`

- [ ] **Step 3: Implement the result dialog**

In `App.vue`, load non-archived regression Datasets when opening the dialog. Support radio/select choice for existing versus new, optional description/reason, validation, loading guard, error display, and a success action that switches to Dataset management with the target Dataset selected. Keep rerun controls unchanged.

- [ ] **Step 4: Implement Dataset presentation**

Add `回归集` badges in list and evaluation selectors. In the Case editor, render provenance fields read-only while leaving ordinary Case fields editable. Do not let form serialization clear provenance.

- [ ] **Step 5: Run typecheck, build, and browser tests**

Run:

```bash
cd web
npm run typecheck
npm run build
npm run test:e2e
```

Expected: all desktop and mobile scenarios pass.

- [ ] **Step 6: Commit**

```bash
git add web/src/App.vue web/src/pages/DatasetWorkspace.vue web/src/components/dataset/DatasetList.vue web/src/components/dataset/CaseEditor.vue web/src/style.css web/tests/demo.spec.ts web/tests/dataset.spec.ts
git commit -m "feat: add regression dataset web workflow"
```

### Task 7: Full verification and status documentation

**Files:**
- Modify: `docs/dataset/implementation-plan.md`
- Modify: `docs/progress.md`

**Interfaces:**
- Records only verified implementation status and commands.

- [ ] **Step 1: Run complete backend verification**

Run: `PYTHONPATH=src python3 -m pytest -q`

Expected: zero failures.

- [ ] **Step 2: Run complete frontend verification**

Run:

```bash
cd web
npm run typecheck
npm run build
npm run test:e2e
```

Expected: zero type errors, successful build, zero Playwright failures.

- [ ] **Step 3: Verify diff and compatibility boundaries**

Run:

```bash
git diff --check feature/single-case-rerun...HEAD
git status --short
```

Confirm `docs/dataset/generation-plan.md` remains untracked and absent from the diff.

- [ ] **Step 4: Update documentation with actual test counts**

Mark the regression-set Dataset workflow implemented while leaving whole-Run comparison and Result Center deferred. Use counts from Steps 1–2 rather than estimates.

- [ ] **Step 5: Commit documentation**

```bash
git add docs/dataset/implementation-plan.md docs/progress.md
git commit -m "docs: record regression dataset workflow"
```
