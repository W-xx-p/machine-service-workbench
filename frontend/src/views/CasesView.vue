<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorMessage } from '../services/api'
import StatusBadge from '../components/StatusBadge.vue'

interface CaseRow { id: number; case_no: string; title: string; model_code: string; alarm_code?: string; symptom: string; root_cause: string; resolution: string; verification: string; risk_level: string; data_classification: string }
const cases = ref<CaseRow[]>([]); const selected = ref<CaseRow | null>(null); const query = ref(''); const error = ref('')
async function load() { try { cases.value = (await api.get('/cases', { params: { query: query.value || undefined } })).data; selected.value = cases.value[0] || null } catch (err) { error.value = errorMessage(err) } }
onMounted(load)
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><p class="eyebrow">SERVICE CASES</p><h1>维修案例</h1><p>复用已审核的处理经验，同时保留验证条件和数据边界。</p></div><div class="search-box">⌕ <input v-model="query" placeholder="搜索案例或现象" @keyup.enter="load" /></div></header>
    <p v-if="error" class="form-error">{{ error }}</p>
    <div class="case-grid">
      <article v-for="item in cases" :key="item.id" class="case-card" :class="{ active: selected?.id === item.id }" @click="selected = item">
        <div><StatusBadge :status="item.risk_level" /><StatusBadge :status="item.data_classification" /></div><h3>{{ item.title }}</h3><p>{{ item.symptom }}</p><footer><span>{{ item.model_code }}</span><span>{{ item.alarm_code || '无报警码' }}</span><b>{{ item.case_no }}</b></footer>
      </article>
    </div>
    <section v-if="selected" class="panel case-detail">
      <div class="panel-heading"><div><p class="eyebrow">CASE DETAIL</p><h2>{{ selected.title }}</h2></div><strong>{{ selected.case_no }}</strong></div>
      <div class="case-steps"><div><span>01</span><section><small>现场现象</small><p>{{ selected.symptom }}</p></section></div><div><span>02</span><section><small>确认原因</small><p>{{ selected.root_cause }}</p></section></div><div><span>03</span><section><small>处理过程</small><p>{{ selected.resolution }}</p></section></div><div><span>04</span><section><small>关闭验证</small><p>{{ selected.verification }}</p></section></div></div>
      <p class="boundary-note">此处为演示流程案例，不是制造商维修指令；不得直接用于真实设备处置。</p>
    </section>
  </div>
</template>

