<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, errorMessage } from '../services/api'
import { useAuthStore } from '../stores/auth'
import StatusBadge from '../components/StatusBadge.vue'

interface DocumentRow { id: number; title: string; filename: string; doc_type: string; version: string; model_codes: string[]; review_status: string; parse_status: string; parse_message?: string; created_at: string }
const auth = useAuthStore()
const documents = ref<DocumentRow[]>([])
const showUpload = ref(false)
const loading = ref(false)
const error = ref('')
const success = ref('')
const file = ref<File | null>(null)
const form = reactive({ title: '', doc_type: 'manual', version: '1.0', model_codes: '', source_url: '' })

async function load() { try { documents.value = (await api.get('/documents')).data } catch (err) { error.value = errorMessage(err) } }
onMounted(load)
function pick(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] || null; if (file.value && !form.title) form.title = file.value.name.replace(/\.[^.]+$/, '') }
async function upload() {
  if (!file.value) return
  loading.value = true; error.value = ''; success.value = ''
  const payload = new FormData(); Object.entries(form).forEach(([key, value]) => payload.append(key, value)); payload.append('file', file.value)
  try { const { data } = await api.post('/documents', payload); success.value = data.parse_message; showUpload.value = false; await load() }
  catch (err) { error.value = errorMessage(err) } finally { loading.value = false }
}
async function review(id: number, status: 'published' | 'rejected' | 'deprecated') { try { await api.patch(`/documents/${id}/review`, { status }); await load() } catch (err) { error.value = errorMessage(err) } }
</script>

<template>
  <div class="page-shell">
    <header class="page-header"><div><p class="eyebrow">CONTROLLED DOCUMENTS</p><h1>文档中心</h1><p>资料经过解析和人工审核后，才能进入问答检索。</p></div><button class="primary-button" @click="showUpload = !showUpload">＋ 导入资料</button></header>
    <p v-if="error" class="form-error">{{ error }}</p><p v-if="success" class="form-success">{{ success }}</p>
    <form v-if="showUpload" class="upload-panel panel" @submit.prevent="upload">
      <div class="panel-heading"><div><p class="eyebrow">NEW DOCUMENT</p><h2>导入受控资料</h2></div><button type="button" class="icon-button" @click="showUpload = false">×</button></div>
      <div class="form-grid"><label>资料名称<input v-model="form.title" required /></label><label>资料类型<select v-model="form.doc_type"><option value="manual">使用说明书</option><option value="alarm_manual">报警手册</option><option value="parts_catalog">备件目录</option><option value="service_bulletin">服务通告</option><option value="case_archive">维修案例</option></select></label><label>版本<input v-model="form.version" required /></label><label>适用机型<input v-model="form.model_codes" placeholder="多个型号用逗号分隔" /></label><label class="span-2">公开来源网址（企业内部资料留空）<input v-model="form.source_url" type="url" /></label></div>
      <label class="drop-zone"><input type="file" accept=".pdf,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.txt,.md,.csv,.json" required @change="pick" /><span>⇧</span><strong>{{ file?.name || '选择 PDF、Office、图片或文本资料' }}</strong><small>单文件不超过 30 MB；扫描件将由 Docling OCR 解析</small></label>
      <div class="form-actions"><p>上传不等于发布。审核人员需核对版本、机型和来源。</p><button class="primary-button" :disabled="loading">{{ loading ? '正在解析…' : '上传并解析' }}</button></div>
    </form>
    <section class="table-panel panel">
      <div class="table-head"><span>资料</span><span>适用机型</span><span>解析</span><span>审核</span><span>更新时间</span><span>操作</span></div>
      <div v-if="!documents.length" class="empty-row">还没有导入资料</div>
      <div v-for="doc in documents" :key="doc.id" class="table-row">
        <div class="doc-name"><span>▤</span><div><strong>{{ doc.title }}</strong><small>{{ doc.filename }} · v{{ doc.version }}</small></div></div>
        <span>{{ doc.model_codes.join('、') || '未限定' }}</span><StatusBadge :status="doc.parse_status" /><StatusBadge :status="doc.review_status" /><span>{{ new Date(doc.created_at).toLocaleDateString() }}</span>
        <div class="row-actions"><button v-if="auth.canReview && doc.parse_status === 'complete' && doc.review_status !== 'published'" @click="review(doc.id, 'published')">发布</button><button v-if="auth.canReview && doc.review_status === 'pending'" @click="review(doc.id, 'rejected')">驳回</button><button v-if="auth.canReview && doc.review_status === 'published'" @click="review(doc.id, 'deprecated')">废止</button></div>
      </div>
    </section>
  </div>
</template>

