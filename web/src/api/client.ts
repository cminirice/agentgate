export interface Version { id: string; label: string }
export interface DatasetOption { id: string; name: string; version: string; case_count: number; description: string }
export interface EvaluatorOption { id: string; name: string; kind: string; version: string; metric: string }
export interface Run { id: string; status: string; snapshot: { target: { version: string }; dataset: { id: string; name: string; cases: Case[] }; evaluators: EvaluatorOption[] } }
export interface Case { id: string; name: string }
export interface Evidence { trace_id: string; span_ids: string[]; description: string }
export interface Result { case_id: string; evaluator_id: string; evaluator_name: string; verdict: 'pass'|'fail'|'review'; score: number; reason: string; primary_failure_step?: string; evidence: Evidence[] }
export interface Gate { verdict: 'pass'|'fail'; passed: number; failed: number; review: number; score: number; threshold: number; reason: string }
export interface Metric { key: string; label: string; score: number; passed: number; total: number }
export interface Report { run: Run; results: Result[]; gate: Gate; metrics: Metric[] }
export interface Trace { case_id: string; spans: { id: string; name: string; kind: string; sequence: number; attributes: Record<string, unknown> }[]; final_state: Record<string, unknown> }
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
