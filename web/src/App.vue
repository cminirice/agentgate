<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type Overview, type Report, type Run, type Trace, type Version } from './api/client'

const overview = ref<Overview>({ total_runs: 0, completed_runs: 0, case_count: 0, latest: null })
const versions = ref<Version[]>([]); const runs = ref<Run[]>([]); const selectedVersion = ref('loan-agent-v2-fixed')
const report = ref<Report|null>(null); const trace = ref<Trace|null>(null); const loading = ref(false); const traceOpen = ref(false)
const caseNames = computed(() => Object.fromEntries((report.value?.run.snapshot.dataset.cases ?? []).map(c => [c.id, c.name])))
const failed = computed(() => report.value?.results.filter(item => item.verdict === 'fail') ?? [])
const percent = computed(() => Math.round((report.value?.gate.score ?? 0) * 100))

async function refresh() {
  const [summary, targetVersions, recentRuns] = await Promise.all([api.overview(), api.versions(), api.runs()])
  overview.value = summary; versions.value = targetVersions; runs.value = recentRuns
  if (!report.value && summary.latest) report.value = summary.latest
}
async function launch() {
  loading.value = true
  try { const run = await api.launch(selectedVersion.value); report.value = await api.report(run.id); await refresh(); ElMessage.success('评估已完成并持久化') }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '评估失败') }
  finally { loading.value = false }
}
async function openRun(id: string) { report.value = await api.report(id); trace.value = null }
async function openTrace(caseId: string) { if (!report.value) return; trace.value = await api.trace(report.value.run.id, caseId); traceOpen.value = true }
onMounted(() => refresh().catch(error => ElMessage.error(`无法连接后端：${error.message}`)))
</script>

<template>
  <div class="shell">
    <header><div><p class="eyebrow">AGENT QUALITY GATE</p><h1>AgentGate 评估台</h1><p>用可追溯证据判断目标代理版本是否达到发布门槛。</p></div><el-tag effect="dark" type="success">P1 演示</el-tag></header>
    <main>
      <section class="stats" aria-label="概览">
        <article><span>累计运行</span><strong>{{ overview.total_runs }}</strong></article>
        <article><span>已完成</span><strong>{{ overview.completed_runs }}</strong></article>
        <article><span>演示用例</span><strong>{{ overview.case_count }}</strong></article>
        <article><span>最新门槛</span><strong :class="report?.gate.verdict">{{ report ? (report.gate.verdict === 'pass' ? '通过' : '未通过') : '—' }}</strong></article>
      </section>
      <section class="panel launch">
        <div><h2>发起评估</h2><p>选择明确版本，运行真实贷款审批数据集。</p></div>
        <div class="actions"><el-select v-model="selectedVersion" aria-label="目标版本"><el-option v-for="item in versions" :key="item.id" :label="`${item.label} · ${item.id}`" :value="item.id" /></el-select><el-button type="primary" :loading="loading" @click="launch">立即评估</el-button></div>
      </section>
      <div class="columns">
        <section class="panel"><h2>运行记录</h2><el-table :data="runs" empty-text="暂无运行"><el-table-column label="版本" min-width="205"><template #default="scope">{{ scope.row.snapshot.target.version }}</template></el-table-column><el-table-column prop="status" label="状态" width="105" /><el-table-column label="操作" width="80"><template #default="scope"><el-button link type="primary" @click="openRun(scope.row.id)">查看</el-button></template></el-table-column></el-table></section>
        <section class="panel result" aria-live="polite"><h2>结果摘要</h2><template v-if="report"><div class="score"><el-progress type="dashboard" :percentage="percent" :color="report.gate.verdict === 'pass' ? '#20b486' : '#e85d75'" /><div><el-tag :type="report.gate.verdict === 'pass' ? 'success' : 'danger'" effect="dark">{{ report.gate.verdict === 'pass' ? '发布门槛通过' : '发布门槛未通过' }}</el-tag><p>{{ report.gate.passed }} 项通过 · {{ report.gate.failed }} 项失败 · 门槛 {{ Math.round(report.gate.threshold * 100) }}%</p></div></div><h3>失败用例与证据</h3><el-empty v-if="failed.length === 0" description="没有失败项" :image-size="70" /><button v-for="item in failed" :key="`${item.case_id}-${item.evaluator_name}`" class="failure" @click="openTrace(item.case_id)"><span><b>{{ caseNames[item.case_id] }}</b><small>{{ item.evaluator_name }} · {{ item.reason }}</small></span><em>查看轨迹 →</em></button></template><el-empty v-else description="运行评估后显示结果" /></section>
      </div>
    </main>
    <el-drawer v-model="traceOpen" title="失败用例轨迹" size="min(520px, 92vw)"><template v-if="trace"><p class="trace-case">{{ caseNames[trace.case_id] }}</p><el-timeline><el-timeline-item v-for="span in trace.spans" :key="span.id" :timestamp="`步骤 ${span.sequence}`" placement="top"><el-card shadow="never"><b>{{ span.name }}</b><el-tag size="small">{{ span.kind }}</el-tag><pre>{{ JSON.stringify(span.attributes, null, 2) }}</pre></el-card></el-timeline-item></el-timeline><h3>最终状态</h3><pre>{{ JSON.stringify(trace.final_state, null, 2) }}</pre></template></el-drawer>
  </div>
</template>
