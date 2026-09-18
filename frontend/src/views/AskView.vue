<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { api, errorMessage } from '../services/api'
import StatusBadge from '../components/StatusBadge.vue'

interface Machine { code: string; name: string }
interface Citation { title: string; source_type: string; source_url?: string; section?: string; version?: string; data_classification: string; model_codes: string[] }
interface RelationPath { path: string[]; relation: string; source_title: string; source_url?: string; source_section?: string; data_classification: string }
interface MaintenanceContext { model_code?: string; serial_number?: string; alarm_code?: string; symptom?: string; completed_checks: string[]; latest_feedback?: string; status: string; inherited_fields: string[]; history_turns_used: number }
interface ChatMessage { role: 'user' | 'assistant'; content: string; citations?: Citation[]; relationPaths?: RelationPath[]; graphNotice?: string; contextNotice?: string; confidence?: number; messageId?: number; missing?: string[] }

const machines = ref<Machine[]>([])
const modelCode = ref('')
const serialNumber = ref('')
const question = ref('')
const conversationId = ref<number | null>(null)
const activeContext = ref<MaintenanceContext | null>(null)
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const error = ref('')
const feed = ref<HTMLElement | null>(null)
const suggestions = ['VMC1000II 的主轴转速和行程是多少？', 'VMC1000II 出现 ATC-1001 应该先检查什么？', 'V8H 连续加工后主轴温升异常怎么排查？']
const statusLabels: Record<string, string> = { collecting_information: '待补充信息', troubleshooting: '排查中', investigating: '继续排查', resolved: '已恢复' }

onMounted(async () => {
  try { machines.value = (await api.get('/products')).data }
  catch (err) { error.value = errorMessage(err) }
})

async function ask(text?: string) {
  const content = (text || question.value).trim()
  if (!content || loading.value) return
  messages.value.push({ role: 'user', content })
  question.value = ''
  loading.value = true; error.value = ''
  await nextTick(); feed.value?.scrollTo({ top: feed.value.scrollHeight, behavior: 'smooth' })
  try {
    const { data } = await api.post('/qa/ask', {
      question: content,
      model_code: modelCode.value || null,
      serial_number: serialNumber.value.trim() || null,
      conversation_id: conversationId.value,
    })
    conversationId.value = data.conversation_id
    activeContext.value = data.context
    if (data.context.model_code) modelCode.value = data.context.model_code
    if (data.context.serial_number) serialNumber.value = data.context.serial_number
    messages.value.push({ role: 'assistant', content: data.answer, citations: data.citations, relationPaths: data.relation_paths, graphNotice: data.graph_notice, contextNotice: data.context_notice, confidence: data.confidence, messageId: data.message_id, missing: data.missing_information })
  } catch (err) { error.value = errorMessage(err) }
  finally { loading.value = false; await nextTick(); feed.value?.scrollTo({ top: feed.value.scrollHeight, behavior: 'smooth' }) }
}

async function rate(messageId: number | undefined, rating: number) {
  if (!messageId) return
  await api.post('/qa/feedback', { message_id: messageId, rating })
}

async function clearFaultContext() {
  if (!conversationId.value || loading.value) return
  loading.value = true; error.value = ''
  try {
    activeContext.value = (await api.post(`/qa/conversations/${conversationId.value}/context/reset`)).data
    modelCode.value = ''; serialNumber.value = ''
  } catch (err) { error.value = errorMessage(err) }
  finally { loading.value = false }
}

function startNewFault() {
  conversationId.value = null
  activeContext.value = null
  messages.value = []
  modelCode.value = ''
  serialNumber.value = ''
  question.value = ''
  error.value = ''
}

function onModelChange() {
  if (activeContext.value?.model_code && modelCode.value !== activeContext.value.model_code) {
    serialNumber.value = ''
  }
}
</script>

<template>
  <div class="ask-layout">
    <aside class="context-panel">
      <p class="eyebrow">MACHINE CONTEXT</p><h2>设备上下文</h2>
      <label>机床型号<select v-model="modelCode" @change="onModelChange"><option value="">暂不指定</option><option v-for="item in machines" :key="item.code" :value="item.code">{{ item.code }}</option></select></label>
      <label>序列号<input v-model="serialNumber" placeholder="例如 SN20260001" maxlength="80" /></label>
      <div v-if="activeContext" class="active-context">
        <div class="active-context-heading"><strong>当前维修会话</strong><span :class="activeContext.status">{{ statusLabels[activeContext.status] || activeContext.status }}</span></div>
        <dl>
          <template v-if="activeContext.model_code"><dt>机型</dt><dd>{{ activeContext.model_code }}</dd></template>
          <template v-if="activeContext.serial_number"><dt>序列号</dt><dd>{{ activeContext.serial_number }}</dd></template>
          <template v-if="activeContext.alarm_code"><dt>报警</dt><dd>{{ activeContext.alarm_code }}</dd></template>
        </dl>
        <div v-if="activeContext.completed_checks.length" class="completed-checks"><small>已完成检查</small><span v-for="(item, index) in activeContext.completed_checks" :key="index">✓ {{ item }}</span></div>
        <p v-if="activeContext.latest_feedback">{{ activeContext.latest_feedback }}</p>
        <small v-if="activeContext.history_turns_used">本轮参考最近 {{ activeContext.history_turns_used }} 条用户描述</small>
        <div class="context-actions"><button type="button" @click="clearFaultContext">清空上下文</button><button type="button" @click="startNewFault">新故障会话</button></div>
      </div>
      <div class="context-tip"><strong>怎样获得更可靠的结果？</strong><p>请同时提供型号、序列号、完整报警码、发生步骤和现场现象。</p></div>
      <div class="graph-coverage-tip"><strong>知识图谱试点范围</strong><p>当前覆盖 VMC II 的换刀系统，包含 VMC850II、VMC1000II、VMC1200II 与 ATC-1001 样板链路。其他问题自动使用结构化数据与文档检索。</p></div>
      <div class="boundary-list"><span>✓ 只检索已发布知识</span><span>✓ 展示来源与版本</span><span>✓ 信息不足时明确拒答</span><span>× 不提供绕过安全互锁的方法</span></div>
    </aside>
    <section class="chat-panel">
      <header><div><p class="eyebrow">ASSISTED TROUBLESHOOTING</p><h1>故障辅助</h1></div><span class="mode-pill">工程师确认模式</span></header>
      <div ref="feed" class="chat-feed">
        <div v-if="!messages.length" class="chat-empty">
          <div class="empty-orbit">◇</div><h2>从一个具体问题开始</h2><p>系统会先识别机型和报警，再关联已发布资料、演示知识与相似案例。</p>
          <button v-for="item in suggestions" :key="item" @click="ask(item)">{{ item }} <span>→</span></button>
        </div>
        <article v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
          <div class="message-avatar">{{ message.role === 'user' ? '我' : '机' }}</div>
          <div class="message-body">
            <div class="message-content">{{ message.content }}</div>
            <div v-if="message.missing?.length" class="missing-info">还需补充：{{ message.missing.join('、') }}</div>
            <div v-if="message.contextNotice" class="context-usage-notice"><span>↻</span>{{ message.contextNotice }}</div>
            <div v-if="message.graphNotice" class="graph-usage-notice" :class="{ covered: message.relationPaths?.length }"><span>◇</span>{{ message.graphNotice }}</div>
            <div v-if="message.relationPaths?.length" class="graph-paths">
              <strong>知识图谱关联路径</strong>
              <a v-for="(item, pathIndex) in message.relationPaths" :key="pathIndex" :href="item.source_url || undefined" :target="item.source_url ? '_blank' : undefined" rel="noopener noreferrer">
                <div class="graph-path-line"><span v-for="(node, nodeIndex) in item.path" :key="nodeIndex"><b>{{ node }}</b><i v-if="nodeIndex < item.path.length - 1">→</i></span></div>
                <small>{{ item.relation }} · {{ item.source_section || item.source_title }}</small>
                <StatusBadge :status="item.data_classification" />
              </a>
              <p>图谱用于说明关联和限定检索范围；演示关系不能直接作为维修或采购依据。</p>
            </div>
            <div v-if="message.citations?.length" class="citations">
              <strong>依据与适用范围</strong>
              <a v-for="(citation, cIndex) in message.citations" :key="cIndex" :href="citation.source_url || undefined" :target="citation.source_url ? '_blank' : undefined" rel="noopener noreferrer">
                <span>{{ cIndex + 1 }}</span><div><b>{{ citation.title }}</b><small>{{ citation.section || citation.source_type }} · {{ citation.version || '无版本' }}</small></div><StatusBadge :status="citation.data_classification" />
              </a>
            </div>
            <div v-if="message.role === 'assistant'" class="message-actions"><span>置信度 {{ Math.round((message.confidence || 0) * 100) }}%</span><button @click="rate(message.messageId, 1)">有帮助</button><button @click="rate(message.messageId, -1)">需改进</button></div>
          </div>
        </article>
        <article v-if="loading" class="message assistant"><div class="message-avatar">机</div><div class="typing"><i></i><i></i><i></i></div></article>
      </div>
      <p v-if="error" class="form-error inset">{{ error }}</p>
      <form class="chat-input" @submit.prevent="ask()">
        <textarea v-model="question" placeholder="描述报警码、现象和发生步骤…" rows="2" @keydown.enter.exact.prevent="ask()"></textarea>
        <button class="primary-button" :disabled="loading || !question.trim()">发送 ↑</button>
        <small>回答仅供辅助，涉及人身与设备安全时以企业受控规程和授权工程师判断为准。</small>
      </form>
    </section>
  </div>
</template>
