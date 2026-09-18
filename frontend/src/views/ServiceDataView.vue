<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api, errorMessage } from '../services/api'
import StatusBadge from '../components/StatusBadge.vue'

interface Machine { code: string }
interface Alarm { id: number; code: string; title: string; severity: string; system: string; applies_to: string[]; symptoms: string[]; possible_causes: string[]; checks: string[]; stop_conditions: string[]; data_classification: string }
interface Part { id: number; part_no: string; name: string; category: string; applies_to: string[]; replaces: string[]; key_specs: Record<string,string>; verification_notes: string[]; data_classification: string }
const tab = ref<'alarms'|'parts'>('alarms'); const machines = ref<Machine[]>([]); const modelCode = ref(''); const query = ref(''); const alarms = ref<Alarm[]>([]); const parts = ref<Part[]>([]); const selectedAlarm = ref<Alarm|null>(null); const selectedPart = ref<Part|null>(null); const error = ref('')
async function load() {
  try {
    if (tab.value === 'alarms') { alarms.value = (await api.get('/alarms', { params: { model_code: modelCode.value || undefined, query: query.value || undefined } })).data; selectedAlarm.value = alarms.value[0] || null }
    else { parts.value = (await api.get('/parts', { params: { model_code: modelCode.value || undefined, query: query.value || undefined } })).data; selectedPart.value = parts.value[0] || null }
  } catch (err) { error.value = errorMessage(err) }
}
onMounted(async () => { machines.value = (await api.get('/products')).data; await load() })
watch([tab, modelCode], load)
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><p class="eyebrow">ALARMS & PARTS</p><h1>报警与备件</h1><p>先限定机型，再查看排查路径或备件核对条件。</p></div><div class="segmented"><button :class="{ active: tab === 'alarms' }" @click="tab = 'alarms'">报警路径</button><button :class="{ active: tab === 'parts' }" @click="tab = 'parts'">备件核对</button></div></header>
    <div class="filter-bar"><label>机型<select v-model="modelCode"><option value="">全部机型</option><option v-for="item in machines" :key="item.code" :value="item.code">{{ item.code }}</option></select></label><label>关键词<input v-model="query" :placeholder="tab === 'alarms' ? '报警码、系统或现象' : '备件号、名称或类别'" @keyup.enter="load" /></label><button class="primary-button" @click="load">查询</button></div>
    <p v-if="error" class="form-error">{{ error }}</p>
    <div v-if="tab === 'alarms'" class="master-detail service-layout">
      <section class="record-list"><button v-for="item in alarms" :key="item.id" :class="{ active: selectedAlarm?.id === item.id }" @click="selectedAlarm = item"><span class="machine-glyph">!</span><div><strong>{{ item.code }}</strong><small>{{ item.title }} · {{ item.system }}</small></div><StatusBadge :status="item.severity" /></button><div v-if="!alarms.length" class="empty-row">没有匹配的已发布报警知识</div></section>
      <section v-if="selectedAlarm" class="detail-card service-detail"><div class="knowledge-title"><div><StatusBadge :status="selectedAlarm.data_classification" /><h2>{{ selectedAlarm.code }} · {{ selectedAlarm.title }}</h2></div><StatusBadge :status="selectedAlarm.severity" /></div><h3>适用机型</h3><div class="tag-list"><span v-for="code in selectedAlarm.applies_to" :key="code">{{ code }}</span></div><div class="service-columns"><div><h3>可能原因</h3><ol><li v-for="item in selectedAlarm.possible_causes" :key="item">{{ item }}</li></ol></div><div><h3>建议检查顺序</h3><ol><li v-for="item in selectedAlarm.checks" :key="item">{{ item }}</li></ol></div></div><h3>必须停止并升级的条件</h3><ul class="stop-list"><li v-for="item in selectedAlarm.stop_conditions" :key="item">{{ item }}</li></ul><p class="boundary-note">演示报警知识仅用于验证系统流程，不能替代真实机型的受控报警手册。</p></section>
    </div>
    <div v-else class="master-detail service-layout">
      <section class="record-list"><button v-for="item in parts" :key="item.id" :class="{ active: selectedPart?.id === item.id }" @click="selectedPart = item"><span class="machine-glyph">⊕</span><div><strong>{{ item.part_no }}</strong><small>{{ item.name }} · {{ item.category }}</small></div><StatusBadge :status="item.data_classification" /></button><div v-if="!parts.length" class="empty-row">没有匹配的已发布备件</div></section>
      <section v-if="selectedPart" class="detail-card service-detail"><div class="knowledge-title"><div><StatusBadge :status="selectedPart.data_classification" /><h2>{{ selectedPart.name }}</h2><p>{{ selectedPart.part_no }}</p></div></div><h3>适用机型</h3><div class="tag-list"><span v-for="code in selectedPart.applies_to" :key="code">{{ code }}</span></div><h3>下单前核对</h3><ol class="check-list"><li v-for="item in selectedPart.verification_notes" :key="item">{{ item }}</li></ol><h3>主数据属性</h3><div class="spec-grid"><div v-for="(value,key) in selectedPart.key_specs" :key="key"><small>{{ key }}</small><strong>{{ value }}</strong></div></div><p class="boundary-note">DEMO 编号禁止用于采购。真实系统必须通过序列号、配置清单和企业备件主数据确认替代关系。</p></section>
    </div>
  </div>
</template>

<style scoped>
.filter-bar{display:flex;align-items:end;gap:10px;margin-bottom:17px;padding:13px;background:#fff;border:1px solid var(--line);border-radius:10px}.filter-bar label{display:grid;gap:5px;font-size:9px;color:#66746f}.filter-bar label:nth-child(2){flex:1}.service-layout{grid-template-columns:380px 1fr}.service-detail h2{margin:8px 0;font-size:21px}.service-detail p{font-size:10px;color:var(--muted)}.service-columns{display:grid;grid-template-columns:1fr 1.2fr;gap:25px}.service-detail ol,.service-detail ul{padding-left:18px;font-size:10px;color:#56645f;line-height:1.75}.stop-list{background:#fbedea;border-radius:8px;padding:12px 12px 12px 28px!important;color:#88483f!important}.check-list{background:#f5f7f4;border-radius:8px;padding:13px 13px 13px 30px!important}@media(max-width:780px){.filter-bar{align-items:stretch;flex-direction:column}.service-layout,.service-columns{grid-template-columns:1fr}}
</style>
