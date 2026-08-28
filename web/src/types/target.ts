// Target/Integrations 域类型
import type { EvaluatorOption } from './evaluator'
import type { DatasetVersion } from './dataset'

export interface Version {
  id: string
  label: string
  is_latest: boolean
  adapter_type?: 'python_fn' | 'http'
  endpoint?: string
  credential_ref?: string | null
}

export interface Run {
  id: string
  status: string
  parent_run_id: string | null
  root_run_id: string | null
  rerun_case_id: string | null
  snapshot: {
    target: {
      ref: { external_target_id: string; external_version_id: string }
      display_name: string
      adapter_type: string
    }
    dataset: DatasetVersion
    evaluator_specs: EvaluatorOption[]
    selected_case_ids: string[] | null
  }
}

// 便捷别名：Run 快照中的 target
export type RunTarget = Run['snapshot']['target']
