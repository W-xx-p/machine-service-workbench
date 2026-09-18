<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, errorMessage } from '../services/api'
import { useAuthStore } from '../stores/auth'

interface GraphCoverage { available: boolean; subsystems: number; models: number; alarms: number; parts: number; cases: number }
interface Metrics {
  products: number; published_documents: number; pending_reviews: number;
  published_alarms: number; cases: number; questions_7d: number; graph_coverage: GraphCoverage
}
interface Health { status: string; database: boolean; neo4j: boolean; llm_configured: boolean }

const auth = useAuthStore()
const metrics = ref<Metrics | null>(null)
const health = ref<Health | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    const [dashboard, system] = await Promise.all([api.get('/dashboard'), api.get('/health')])
    metrics.value = dashboard.data
    health.value = system.data
  } catch (err) { error.value = errorMessage(err) }
})
</script>

<template>
  <div class="page-shell">
    <header class="page-header hero-header">
      <div><p class="eyebrow">OPERATIONS OVERVIEW</p><h1>早上好，{{ auth.user?.display_name }}</h1><p>从已审核知识开始处理今天的售后问题。</p></div>
      <RouterLink class="primary-button" to="/ask">开始故障辅助 <span>→</span></RouterLink>
    </header>
    <p v-if="error" class="form-error">{{ error }}</p>
    <section class="metric-grid">
      <article><span class="metric-icon green">▦</span><div><small>产品型号</small><strong>{{ metrics?.products ?? '—' }}</strong><p>公开样本与企业机型</p></div></article>
      <article><span class="metric-icon blue">▤</span><div><small>已发布文档</small><strong>{{ metrics?.published_documents ?? '—' }}</strong><p>仅发布资料进入问答</p></div></article>
      <article><span class="metric-icon amber">⌛</span><div><small>待审核资料</small><strong>{{ metrics?.pending_reviews ?? '—' }}</strong><p>等待责任人确认</p></div></article>
      <article><span class="metric-icon plum">◇</span><div><small>近 7 日提问</small><strong>{{ metrics?.questions_7d ?? '—' }}</strong><p>全部保留检索审计</p></div></article>
    </section>
    <section class="panel graph-coverage-panel">
      <div class="graph-coverage-heading"><div><p class="eyebrow">KNOWLEDGE GRAPH COVERAGE</p><h2>知识图谱试点覆盖</h2><p>当前优先验证 VMC II 换刀系统；未覆盖问题自动降级为结构化数据与文档检索。</p></div><span :class="metrics?.graph_coverage.available ? 'coverage-live' : 'coverage-offline'">{{ metrics?.graph_coverage.available ? '实时统计' : '图谱不可用' }}</span></div>
      <div class="graph-coverage-stats">
        <div><strong>{{ metrics?.graph_coverage.subsystems ?? '—' }}</strong><small>子系统</small></div>
        <div><strong>{{ metrics?.graph_coverage.models ?? '—' }}</strong><small>覆盖机型</small></div>
        <div><strong>{{ metrics?.graph_coverage.alarms ?? '—' }}</strong><small>关联报警</small></div>
        <div><strong>{{ metrics?.graph_coverage.parts ?? '—' }}</strong><small>关联备件</small></div>
        <div><strong>{{ metrics?.graph_coverage.cases ?? '—' }}</strong><small>关联案例</small></div>
        <RouterLink to="/ask">验证样板路径 →</RouterLink>
      </div>
    </section>
    <section class="dashboard-grid">
      <article class="panel quick-panel">
        <div class="panel-heading"><div><p class="eyebrow">QUICK ACCESS</p><h2>快速开始</h2></div></div>
        <div class="quick-links">
          <RouterLink to="/ask"><span>01</span><div><strong>查询报警与排查路径</strong><p>按机型、报警码和现象检索已发布知识</p></div><b>→</b></RouterLink>
          <RouterLink to="/products"><span>02</span><div><strong>核对机型与公开参数</strong><p>确认产品系列、版本和数据来源</p></div><b>→</b></RouterLink>
          <RouterLink to="/documents"><span>03</span><div><strong>导入企业受控资料</strong><p>解析后需审核发布才能用于问答</p></div><b>→</b></RouterLink>
        </div>
      </article>
      <article class="panel status-panel">
        <div class="panel-heading"><div><p class="eyebrow">SYSTEM STATUS</p><h2>服务状态</h2></div><span class="live-dot">运行中</span></div>
        <dl>
          <div><dt>业务数据库</dt><dd :class="health?.database ? 'ok' : 'warn'">{{ health?.database ? '正常' : '异常' }}</dd></div>
          <div><dt>知识图谱</dt><dd :class="health?.neo4j ? 'ok' : 'muted'">{{ health?.neo4j ? '已连接' : '降级可用' }}</dd></div>
          <div><dt>大模型接口</dt><dd class="muted">{{ health?.llm_configured ? '已配置' : '未启用' }}</dd></div>
          <div><dt>安全模式</dt><dd class="ok">工程师确认</dd></div>
        </dl>
        <div class="safety-card"><strong>首版边界</strong><p>不自动诊断，不修改参数，不控制设备。高风险操作必须升级给授权工程师。</p></div>
      </article>
    </section>
  </div>
</template>
