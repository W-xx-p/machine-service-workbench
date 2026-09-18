<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorMessage } from '../services/api'
import StatusBadge from '../components/StatusBadge.vue'

interface Series { name: string; manufacturer: string }
interface Machine { code: string; name: string; model_version: string; specs: Record<string, string>; source_url: string; source_title: string; data_classification: string; series: Series }
const products = ref<Machine[]>([])
const selected = ref<Machine | null>(null)
const query = ref('')
const error = ref('')

async function load() {
  try { products.value = (await api.get('/products', { params: { query: query.value || undefined } })).data; if (!selected.value) selected.value = products.value[0] || null }
  catch (err) { error.value = errorMessage(err) }
}
onMounted(load)
const specLabels: Record<string, string> = { work_range_xyz_mm: 'X/Y/Z 行程', rapid_traverse_xyz_m_min: 'X/Y/Z 快移速度', spindle_speed_rpm: '主轴转速', spindle_power_kw: '主轴功率', spindle_torque_nm: '主轴扭矩', catalog_note: '目录说明' }
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><p class="eyebrow">PRODUCT MASTER DATA</p><h1>产品档案</h1><p>核对系列、型号、版本和来源，避免跨型号套用知识。</p></div><div class="search-box">⌕ <input v-model="query" placeholder="搜索型号" @keyup.enter="load" /></div></header>
    <p v-if="error" class="form-error">{{ error }}</p>
    <div class="master-detail">
      <section class="record-list">
        <button v-for="item in products" :key="item.code" :class="{ active: selected?.code === item.code }" @click="selected = item">
          <span class="machine-glyph">▦</span><div><strong>{{ item.code }}</strong><small>{{ item.series?.name }}</small></div><b>›</b>
        </button>
      </section>
      <section v-if="selected" class="detail-card">
        <div class="detail-hero"><div><StatusBadge :status="selected.data_classification" /><h2>{{ selected.code }}</h2><p>{{ selected.name }}</p></div><div class="machine-outline">VMC</div></div>
        <div class="detail-meta"><div><small>产品系列</small><strong>{{ selected.series?.name }}</strong></div><div><small>制造商</small><strong>{{ selected.series?.manufacturer }}</strong></div><div><small>资料版本</small><strong>{{ selected.model_version }}</strong></div></div>
        <h3>已核验参数</h3>
        <div class="spec-grid"><div v-for="(value, key) in selected.specs" :key="key"><small>{{ specLabels[String(key)] || key }}</small><strong>{{ value }}</strong><span v-if="String(key).includes('_mm')">mm</span><span v-else-if="String(key).includes('m_min')">m/min</span><span v-else-if="String(key).includes('rpm')">rpm</span><span v-else-if="String(key).includes('_kw')">kW</span><span v-else-if="String(key).includes('_nm')">N·m</span></div></div>
        <div class="source-box"><div><strong>公开数据来源</strong><p>{{ selected.source_title }}</p></div><a :href="selected.source_url" target="_blank" rel="noopener noreferrer">查看原始页面 ↗</a></div>
        <p class="boundary-note">公开目录参数不能代表具体出厂配置。备件匹配和维修前仍需核对序列号、配置清单与企业受控手册。</p>
      </section>
    </div>
  </div>
</template>
