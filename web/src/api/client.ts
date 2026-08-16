export interface Version { id: string; label: string }
export interface DatasetOption { id: string; name: string; version: string; case_count: number; description: string }
export interface EvaluatorOption {
  id: string
  name: string
  kind: 'rule'|'llm_judge'|'hybrid'
  version: string
  dimension: string
  metric: string
  severity: 'standard'|'blocking'
  evaluator_type: string
  operator: string|null
}
export interface Run { id: string; status: string; snapshot: { target: { version: string }; dataset: { id: string; name: string; cases: Case[] }; evaluator_specs: EvaluatorOption[] } }
export interface Case { id: string; name: string }
export interface Evidence { trace_id: string; span_ids: string[]; description: string }
export type Outcome = 'pass'|'fail'|'review'|'not_applicable'|'error'
export interface CheckResult { id: string; name: string; outcome: Outcome; score: number|null; reason: string; evidence: Evidence[] }
export interface Result { case_id: string; evaluator_id: string; evaluator_name: string; evaluator_kind: string; dimension: string; metric: string; severity: 'standard'|'blocking'; outcome: Outcome; score: number|null; reason: string; primary_failure_step?: string; evidence: Evidence[]; checks: CheckResult[] }
export interface Gate { outcome: 'pass'|'fail'; passed: number; failed: number; reviewed: number; not_applicable: number; errors: number; score: number|null; threshold: number; reason: string }
export interface Metric { key: string; label: string; level: 'overall'|'kind'|'dimension'|'metric'; score: number|null; passed: number; failed: number; reviewed: number; not_applicable: number; errors: number; applicable: number; total: number; incomplete: boolean }
export interface Report { run: Run; results: Result[]; gate: Gate; metrics: Metric[] }
export interface Trace { case_id: string; spans: { id: string; name: string; kind: string; sequence: number; attributes: Record<string, unknown> }[]; final_state: Record<string, unknown>; final_output: Record<string, unknown> }
export interface Overview { total_runs: number; completed_runs: number; case_count: number; latest: Report|null }

const json = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init)
  if (!response.ok) throw new Error((await response.json()).detail ?? `HTTP ${response.status}`)
  return response.json()
}

export const api = {
  overview: () => json<Overview>('/api/overview'),
  versions: () => json<Version[]>('/api/versions'),
  datasets: () => json<DatasetOption[]>('/api/datasets'),
  evaluators: () => json<EvaluatorOption[]>('/api/evaluators'),
  runs: () => json<Run[]>('/api/runs'),
  launch: (version: string, datasetId: string, evaluatorIds: string[]) => json<Run>('/api/evaluations', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version, dataset_id: datasetId, evaluator_ids: evaluatorIds }),
  }),
  report: (id: string) => json<Report>(`/api/runs/${id}`),
  trace: (runId: string, caseId: string) => json<Trace>(`/api/runs/${runId}/traces/${caseId}`),
}
