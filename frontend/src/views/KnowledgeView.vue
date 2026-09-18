<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, errorMessage } from '../services/api'
import { useAuthStore } from '../stores/auth'
import StatusBadge from '../components/StatusBadge.vue'

interface Item { id: number; title: string; item_type: string; content: string; applies_to: string[]; source_title: string; source_url?: string; source_section?: string; version: string; confidence: number; review_status: string; data_classification: string }
const auth = useAuthStore(); const items = ref<Item[]>([]); const filter = ref('all'); const selected = ref<Item | null>(null); const error = ref('')
const visible = computed(() => filter.value === 'all' ? items.value : items.value.filter((item) => item.review_status === filter.value))
async function load() { try { items.value = (await api.get('/knowledge')).data; selected.value = visible.value[0] || null } catch (err) { error.value = errorMessage(err) } }
onMounted(load)
async function review(status: 'published' | 'rejected' | 'deprecated') { if (!selected.value) return; try { await api.patch(`/knowledge/${selected.value.id}/review`, { status }); await load() } catch (err) { error.value = errorMessage(err) } }
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><p class="eyebrow">KNOWLEDGE GOVERNANCE</p><h1>知识审核</h1><p>每条知识都保留适用范围、来源、版本、置信度和状态。</p></div><div class="segmented"><button v-for="entry in [['all','全部'],['pending','待审核'],['published','已发布'],['deprecated','已废止']]" :key="entry[0]" :class="{ active: filter === entry[0] }" @click="filter = entry[0]">{{ entry[1] }}</button></div></header>
    <p v-if="error" class="form-error">{{ error }}</p>
    <div class="master-detail knowledge-layout">
      <section class="record-list">
        <button v-for="item in visible" :key="item.id" :class="{ active: selected?.id === item.id }" @click="selected = item"><span class="machine-glyph">◇</span><div><strong>{{ item.title }}</strong><small>{{ item.item_type }} · {{ item.version }}</small></div><StatusBadge :status="item.review_status" /></button>
        <div v-if="!visible.length" class="empty-row">没有符合条件的知识项</div>
      </section>
      <section v-if="selected" class="detail-card knowledge-detail">
        <div class="knowledge-title"><div><StatusBadge :status="selected.data_classification" /><h2>{{ selected.title }}</h2></div><StatusBadge :status="selected.review_status" /></div>
        <div class="confidence"><span>抽取置信度</span><div><i :style="{ width: `${selected.confidence * 100}%` }"></i></div><strong>{{ Math.round(selected.confidence * 100) }}%</strong></div>
        <h3>知识内容</h3><p class="knowledge-content">{{ selected.content }}</p>
        <h3>适用范围</h3><div class="tag-list"><span v-for="code in selected.applies_to" :key="code">{{ code }}</span></div>
        <h3>来源信息</h3><div class="source-box"><div><strong>{{ selected.source_title }}</strong><p>{{ selected.source_section }} · {{ selected.version }}</p></div><a v-if="selected.source_url" :href="selected.source_url" target="_blank" rel="noopener noreferrer">查看来源 ↗</a></div>
        <div v-if="auth.canReview" class="review-actions"><button v-if="selected.review_status !== 'rejected'" class="secondary-button danger" @click="review('rejected')">驳回</button><button v-if="selected.review_status === 'published'" class="secondary-button" @click="review('deprecated')">废止</button><button v-else class="primary-button" @click="review('published')">审核并发布</button></div>
      </section>
    </div>
  </div>
</template>
