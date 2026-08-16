<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type DatasetOption, type EvaluatorOption, type Overview, type Report, type Run, type Trace, type Version } from './api/client'

const overview = ref<Overview>({ total_runs: 0, completed_runs: 0, case_count: 0, latest: null })
const versions = ref<Version[]>([])
const datasets = ref<DatasetOption[]>([])
const evaluators = ref<EvaluatorOption[]>([])
const runs = ref<Run[]>([])
const selectedVersion = ref('loan-agent-v2-fixed')
const selectedDataset = ref('loan-risk-policy')
const selectedEvaluators = ref<string[]>([])
const report = ref<Report|null>(null)
const trace = ref<Trace|null>(null)
const loading = ref(false)
const traceOpen = ref(false)

const caseNames = computed(() => Object.fromEntries((report.value?.run.snapshot.dataset.cases ?? []).map(c => [c.id, c.name])))
const failed = computed(() => report.value?.results.filter(item => item.outcome === 'fail') ?? [])
const selectedAgent = computed(() => versions.value.find(item => item.id === selectedVersion.value))
const selectedDatasetInfo = computed(() => datasets.value.find(item => item.id === selectedDataset.value))

async function refresh() {
  const [summary, targetVersions, datasetOptions, evaluatorOptions, recentRuns] = await Promise.all([
    api.overview(), api.versions(), api.datasets(), api.evaluators(), api.runs(),
  ])
  overview.value = summary
  versions.value = targetVersions
  datasets.value = datasetOptions
  evaluators.value = evaluatorOptions
  runs.value = recentRuns
  if (selectedEvaluators.value.length === 0) selectedEvaluators.value = evaluatorOptions.map(item => item.id)
  if (!report.value && summary.latest) report.value = summary.latest
}

async function launch() {
  if (selectedEvaluators.value.length === 0) return ElMessage.warning('请至少选择一个评估器')
  loading.value = true
  try {
    const run = await api.launch(selectedVersion.value, selectedDataset.value, selectedEvaluators.value)
    report.value = await api.report(run.id)
    await refresh()
    document.querySelector('#result-report')?.scrollIntoView({ behavior: 'smooth' })
    ElMessage.success('评估已完成，指标与证据已持久化')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '评估失败')
  } finally { loading.value = false }
}

async function openRun(id: string) { report.value = await api.report(id); trace.value = null }
async function openTrace(caseId: string) { if (!report.value) return; trace.value = await api.trace(report.value.run.id, caseId); traceOpen.value = true }
const asPercent = (score: number|null) => score === null ? 'N/A' : `${Math.round(score * 100)}%`
const outcomeText = { pass: '通过', fail: '失败', review: '待复核', not_applicable: '不适用', error: '评估错误' }
const outcomeType = (outcome: string) => outcome === 'pass' ? 'success' : outcome === 'not_applicable' ? 'info' : outcome === 'review' ? 'warning' : 'danger'

onMounted(() => refresh().catch(error => ElMessage.error(`无法连接后端：${error.message}`)))
</script>

<template>
  <div class="shell">
    <header>
      <div><p class="eyebrow">AGENT QUALITY GATE</p><h1>AgentGate 评估台</h1><p>配置评估对象，运行用例，并用可追溯指标判断是否达到发布门槛。</p></div>
      <el-tag effect="dark" type="success">P1 演示</el-tag>
    </header>

    <main>
      <section class="region config-region" aria-labelledby="config-title">
        <div class="region-heading"><div><span class="step">01 · EVALUATION SETUP</span><h2 id="config-title">评估配置</h2><p>选择 Agent、数据集与评估器，然后启动一次真实评估。</p></div><div class="run-count">已完成 {{ overview.completed_runs }} 次运行</div></div>

        <div class="config-grid">
          <article class="config-card">
            <div class="card-index">A</div><label>Agent</label>
            <el-select v-model="selectedVersion" data-testid="agent-select" aria-label="Agent 版本">
              <el-option v-for="item in versions" :key="item.id" :label="`${item.label} · ${item.id}`" :value="item.id" />
            </el-select>
            <p>{{ selectedAgent?.label }}，使用确定性 Provider 执行。</p>
          </article>

          <article class="config-card">
            <div class="card-index">D</div><label>Dataset</label>
            <el-select v-model="selectedDataset" data-testid="dataset-select" aria-label="数据集">
              <el-option v-for="item in datasets" :key="item.id" :label="`${item.name} · v${item.version}`" :value="item.id" />
            </el-select>
            <p>{{ selectedDatasetInfo?.description }} · {{ selectedDatasetInfo?.case_count ?? 0 }} 个用例</p>
          </article>

          <article class="config-card evaluator-card">
            <div class="card-index">E</div><label>Evaluators & Metrics</label>
            <div class="evaluator-kinds" aria-label="评估器分类">
              <span class="active-kind">规则评估器</span>
              <span>LLM Judge · P2</span>
              <span>Hybrid · P2</span>
            </div>
            <el-checkbox-group v-model="selectedEvaluators" class="evaluator-list">
              <el-checkbox v-for="item in evaluators" :key="item.id" :value="item.id" border>
                <span class="eval-name">{{ item.name }}</span><small>{{ item.metric }} · {{ item.dimension }}</small>
              </el-checkbox>
            </el-checkbox-group>
          </article>
        </div>

        <div class="launch-bar">
          <div><b>{{ selectedEvaluators.length }}</b> 个评估器已启用 <span>· 结果将写入 SQLite</span></div>
          <el-button type="primary" size="large" :loading="loading" :disabled="selectedEvaluators.length === 0" @click="launch">运行评估 <span>→</span></el-button>
        </div>
      </section>

      <section id="result-report" class="region report-region" aria-labelledby="report-title">
        <div class="region-heading report-heading">
          <div><span class="step">02 · RESULT REPORT</span><h2 id="report-title">结果报告</h2><p v-if="report">{{ report.run.snapshot.target.version }} · {{ report.run.snapshot.dataset.name }}</p><p v-else>运行评估后在此查看指标、失败证据和轨迹。</p></div>
          <el-tag v-if="report" :type="report.gate.outcome === 'pass' ? 'success' : 'danger'" effect="dark" size="large">{{ report.gate.outcome === 'pass' ? '发布门槛通过' : '发布门槛未通过' }}</el-tag>
        </div>

        <template v-if="report">
          <div class="metric-grid" aria-label="评估指标">
            <article v-for="metric in report.metrics" :key="`${metric.level}-${metric.key}`" class="metric-card" :data-testid="`metric-${metric.level}-${metric.key}`">
              <span>{{ metric.label }} · {{ metric.level }}</span><strong>{{ asPercent(metric.score) }}</strong>
              <el-progress :percentage="Math.round((metric.score ?? 0) * 100)" :show-text="false" :stroke-width="7" :color="(metric.score ?? 0) >= .95 ? '#20b486' : '#e85d75'" />
              <small>{{ metric.passed }} 通过 · {{ metric.failed }} 失败 · {{ metric.not_applicable }} 不适用<span v-if="metric.errors"> · {{ metric.errors }} 错误</span></small>
            </article>
            <article class="metric-card gate-card"><span>发布门槛</span><strong>{{ Math.round(report.gate.threshold * 100) }}%</strong><small>{{ report.gate.reason }}</small></article>
          </div>

          <div class="report-grid">
            <article class="report-panel">
              <div class="panel-title"><h3>全部检查结果</h3><el-tag type="danger" plain>{{ failed.length }} 项失败</el-tag></div>
              <div v-for="item in report.results" :key="`${item.case_id}-${item.evaluator_id}`" class="result-item">
                <div class="result-head">
                  <span><b>{{ caseNames[item.case_id] }} · {{ item.evaluator_name }}</b><small>{{ item.reason }}</small></span>
                  <el-tag :type="outcomeType(item.outcome)" size="small">{{ outcomeText[item.outcome] }}</el-tag>
                </div>
                <ul v-if="item.checks.length" class="check-list">
                  <li v-for="check in item.checks" :key="check.id">
                    <span>{{ check.name }} · {{ check.reason }}</span>
                    <el-tag :type="outcomeType(check.outcome)" size="small" effect="plain">{{ outcomeText[check.outcome] }}</el-tag>
                  </li>
                </ul>
                <button v-if="item.outcome === 'fail'" class="trace-link" @click="openTrace(item.case_id)">查看失败轨迹 →</button>
              </div>
            </article>

            <article class="report-panel">
              <div class="panel-title"><h3>最近运行</h3><span>{{ runs.length }} 条</span></div>
              <el-table :data="runs" empty-text="暂无运行" size="small">
                <el-table-column label="Agent" min-width="190"><template #default="scope">{{ scope.row.snapshot.target.version }}</template></el-table-column>
                <el-table-column prop="status" label="状态" width="95" />
                <el-table-column label="操作" width="70"><template #default="scope"><el-button link type="primary" @click="openRun(scope.row.id)">查看</el-button></template></el-table-column>
              </el-table>
            </article>
          </div>
        </template>
        <el-empty v-else description="尚无结果，请先在上方运行评估" />
      </section>
    </main>

    <el-drawer v-model="traceOpen" title="失败用例轨迹" size="min(520px, 92vw)">
      <template v-if="trace"><p class="trace-case">{{ caseNames[trace.case_id] }}</p><el-timeline><el-timeline-item v-for="span in trace.spans" :key="span.id" :timestamp="`步骤 ${span.sequence}`" placement="top"><el-card shadow="never"><b>{{ span.name }}</b><el-tag size="small">{{ span.kind }}</el-tag><pre>{{ JSON.stringify(span.attributes, null, 2) }}</pre></el-card></el-timeline-item></el-timeline><h3>最终状态</h3><pre>{{ JSON.stringify(trace.final_state, null, 2) }}</pre></template>
    </el-drawer>
  </div>
</template>
