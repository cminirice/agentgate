# Regression-set Workflow Design

## Goal

Implement the first regression-set workflow as a specialization of the existing
Dataset and Case workflow. A user can copy a Case from a completed Run into a
regression Dataset draft, review and publish that draft, then evaluate the published
version through the existing Run flow.

The first increment does not add regression-specific execution, batch Run comparison,
Result Center features, Case correction, or automatic regression-set population.

## Product workflow

```text
Completed Run
  -> choose a Case
  -> add it to an existing or new regression Dataset
  -> optionally record a reason
  -> review the regression Dataset draft
  -> publish an immutable DatasetVersion
  -> launch a normal evaluation with chosen Agent and Evaluators
  -> inspect the existing Run report and Trace
```

Only Cases from completed Runs can enter this workflow. The source Case is always read
from the immutable RunSnapshot, never from a current Dataset draft or a later published
version.

## Domain model

### Dataset purpose

Add a backward-compatible Dataset purpose:

```python
class DatasetPurpose(StrEnum):
    STANDARD = "standard"
    REGRESSION = "regression"


class Dataset(DomainModel):
    # Existing fields remain unchanged.
    purpose: DatasetPurpose = DatasetPurpose.STANDARD
```

Old persisted Dataset payloads omit `purpose` and therefore load as `standard`.
Purpose is immutable after Dataset creation. A standard Dataset cannot be converted to
a regression Dataset, or vice versa.

### Case provenance

Add optional immutable provenance to Case:

```python
class CaseProvenance(DomainModel):
    source_type: Literal["run_result"] = "run_result"
    source_run_id: str
    source_dataset_id: str
    source_dataset_version: int
    source_case_id: str
    captured_at: datetime
    reason: str = ""


class Case(DomainModel):
    # Existing fields remain unchanged.
    provenance: CaseProvenance | None = None
```

Normal Dataset Cases may omit provenance. A Case added through the regression workflow
receives a new internal `Case.id` while `provenance.source_case_id` preserves the source
identity.

Published DatasetVersion hashing already includes serialized Cases. To preserve hashes
stored before this field existed, hash construction removes `provenance` when its value is
`None`. Non-null provenance remains in the hash. Dataset purpose belongs to Dataset
identity rather than DatasetVersion content and therefore is not added to the version
hash.

## Membership and duplicate rules

Within one regression Dataset, one source Case may appear at most once. Membership is
unique by:

```text
(regression_dataset_id, provenance.source_case_id)
```

Consequences:

- adding the same source Case from another Run is rejected;
- adding the same source Case from another Dataset version is rejected because Case IDs
  remain stable across versions;
- the same source Case may be added to different regression Datasets;
- different source Case IDs with identical content are allowed;
- Cases without regression provenance are ignored by the source-identity uniqueness
  check; they do not represent a previously imported source Case.

The duplicate check covers the effective draft contents. When a draft is based on the
latest published version, inherited members are included automatically.

## Dataset and draft behavior

Regression Datasets reuse all existing Dataset behaviors:

- catalog persistence and archive;
- one active draft per Dataset;
- immutable published versions;
- Case removal, ordering, validation, and publication;
- normal evaluation launch with an explicit published version.

Adding a Case behaves as follows:

1. For a new regression Dataset, create the Dataset and an empty draft.
2. For an existing regression Dataset with an active draft, append to that draft.
3. For an existing regression Dataset without a draft, create a draft based on its latest
   published version and append to it.

The add operation is atomic from the service caller's perspective. Validation failures
must not create a partial Dataset, draft, or Case member. For the new-target mode, add a
repository operation that stores the Dataset and initial draft in one SQLite transaction.
Existing-target mode persists a single updated draft payload.

## Service contract

Add a focused application service operation, exposed through the control-plane service:

```python
add_case_to_regression_dataset(
    *,
    run_id: str,
    case_id: str,
    regression_dataset_id: str | None,
    new_dataset_name: str | None,
    new_dataset_description: str = "",
    reason: str = "",
) -> tuple[Dataset, DatasetVersion, Case]
```

Exactly one target mode is valid:

- `regression_dataset_id` selects an existing regression Dataset; or
- `new_dataset_name` creates a new regression Dataset.

The operation validates, in order:

1. the source Run exists and is completed;
2. the Case exists in the source RunSnapshot;
3. the selected target exists, is not archived, and has regression purpose;
4. the target draft does not already contain the source Case identity;
5. the copied Case and resulting draft satisfy current domain validation.

The copied Case content comes entirely from the source snapshot. The operation changes
only its internal ID and adds provenance.

## HTTP API

Add:

```text
POST /api/runs/{run_id}/cases/{case_id}/regression
```

Existing-target request:

```json
{
  "regression_dataset_id": "dataset-id",
  "reason": "Prevent direct approval of high-risk loans"
}
```

New-target request:

```json
{
  "new_dataset_name": "Loan approval regressions",
  "new_dataset_description": "Verified bad cases from evaluation runs",
  "reason": "Prevent direct approval of high-risk loans"
}
```

The response contains the target Dataset summary, updated draft, and newly copied Case.

Error mapping:

- unknown Run, Case, or target Dataset: `404`;
- non-completed Run, archived/standard target, invalid target mode, duplicate source Case,
  or invalid draft: `422`;
- unexpected persistence failure: existing server error behavior, with no partial write.

Dataset create/list responses expose `purpose`. Existing Dataset endpoints otherwise keep
their contracts.

## Web interaction

### Result report

Every Case group in a completed Run shows `加入回归集` next to Trace and rerun actions.
The dialog provides:

- source Case, Dataset version, Run, and Agent version as fixed information;
- a choice between an existing regression Dataset and a new one;
- existing-target selection filtered to non-archived regression Datasets;
- new Dataset name and optional description;
- optional reason;
- disabled submit and loading state during submission.

On success, the original report remains visible. A success message includes the target
regression Dataset name and a link/button to open its draft in Dataset management.

### Dataset workspace

Dataset lists and selectors display a `回归集` badge for regression purpose. Regression
Datasets otherwise use the same editor and version controls as standard Datasets.

For a Case with provenance, the editor displays source Run, source Dataset/version,
source Case ID, captured time, and reason as read-only information. Normal Case fields
remain editable in the draft. Editing those fields does not change provenance or permit
the same source Case to be added again.

Published regression Dataset versions launch through the existing evaluation setup. The
user independently selects Agent version and Evaluators; the Dataset does not persist or
imply an evaluation configuration.

## Compatibility and persistence

SQLite stores Dataset and DatasetVersion JSON payloads, so no new table or SQL migration
is required. Existing payloads load through field defaults. The repository protocol and
SQLite adapter add `save_dataset_with_draft(dataset, draft)` for atomic new-target
creation; it inserts both JSON payloads in one transaction and rolls back both on error.

JSON import/export must preserve Dataset purpose and Case provenance when present. Older
exports without those fields continue to import as standard Datasets with ordinary Cases.
Excel support lives in a separate feature branch and is not a dependency of this PR.

## Testing

Domain and service tests cover:

- old Dataset and Case payload compatibility;
- creation of standard and regression Datasets;
- copying the exact source RunSnapshot Case with a new internal ID;
- provenance values and immutable published-version hashing;
- existing target with and without an active draft;
- new target creation;
- duplicate rejection by source Case ID, including another Run and Dataset version;
- allowing identical content with different source Case IDs;
- rejecting unknown/non-completed Runs, unknown Cases, standard targets, and archived
  targets without partial writes;
- publishing and running a regression Dataset through the normal RunEngine;
- JSON round-trip preservation.

API tests cover both target modes, status mappings, and response payloads.

Web tests cover desktop and mobile flows for creating a regression Dataset from a failed
Case, rejecting a duplicate, opening the draft, publishing it, and launching it through
the existing evaluation page. Existing standard Dataset and Single-Case rerun scenarios
must remain green.

## Deferred work

The following remain outside this PR:

- comparing two complete regression Runs;
- Result Center filters, confusion matrices, and A/B winner decisions;
- automatic Case correction or write-back;
- automatic regression membership from failures;
- evaluator profiles or evaluator binding to a Dataset;
- regression-specific schedulers, queues, retries, or release gates;
- Excel-specific regression provenance columns.
