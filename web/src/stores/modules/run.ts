// Run 域状态（评估配置选择）
// 对齐 App.vue L12-L14：selectedVersion/selectedDataset/selectedEvaluators
import { defineStore } from 'pinia'

interface RunConfigState {
  selectedVersion: string
  selectedDataset: string
  selectedEvaluators: string[]
  loading: boolean
}

export const useRunStore = defineStore('run', {
  state: (): RunConfigState => ({
    selectedVersion: 'loan-agent-v2-fixed',
    selectedDataset: 'loan-risk-policy',
    selectedEvaluators: [],
    loading: false,
  }),
  actions: {
    setVersion(version: string) {
      this.selectedVersion = version
    },
    setDataset(datasetId: string) {
      this.selectedDataset = datasetId
    },
    setEvaluators(ids: string[]) {
      this.selectedEvaluators = ids
    },
    resetEvaluatorsIfEmpty(evaluatorIds: string[]) {
      if (this.selectedEvaluators.length === 0) {
        this.selectedEvaluators = [...evaluatorIds]
      }
    },
  },
})
