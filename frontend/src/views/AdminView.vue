<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, errorMessage } from '../services/api'
import { useAuthStore } from '../stores/auth'

interface UserRow {
  id: number
  username: string
  display_name: string
  role: string
  active: boolean
  locked_until?: string | null
  last_login_at?: string | null
}

interface AuditRow {
  id: number
  username: string
  action: string
  target_type: string
  target_id?: string
  created_at: string
}

const auth = useAuthStore()
const users = ref<UserRow[]>([])
const logs = ref<AuditRow[]>([])
const error = ref('')
const showUser = ref(false)
const busyUserId = ref<number | null>(null)
const form = reactive({ username: '', display_name: '', password: '', role: 'engineer' })

function isLocked(user: UserRow) {
  return Boolean(user.locked_until && new Date(user.locked_until).getTime() > Date.now())
}

async function load() {
  try {
    error.value = ''
    logs.value = (await api.get('/admin/audit')).data
    if (auth.isAdmin) users.value = (await api.get('/admin/users')).data
  } catch (err) {
    error.value = errorMessage(err)
  }
}

onMounted(load)

async function createUser() {
  try {
    error.value = ''
    await api.post('/admin/users', form)
    showUser.value = false
    Object.assign(form, { username: '', display_name: '', password: '', role: 'engineer' })
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  }
}

async function changeStatus(user: UserRow) {
  const action = user.active ? '停用' : '启用'
  if (!window.confirm(`确认${action}账号“${user.username}”吗？`)) return
  busyUserId.value = user.id
  try {
    error.value = ''
    await api.patch(`/admin/users/${user.id}/status`, { active: !user.active })
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busyUserId.value = null
  }
}

async function unlock(user: UserRow) {
  busyUserId.value = user.id
  try {
    error.value = ''
    await api.post(`/admin/users/${user.id}/unlock`)
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busyUserId.value = null
  }
}
</script>

<template>
  <div class="page-shell">
    <header class="page-header">
      <div>
        <p class="eyebrow">ACCESS & AUDIT</p>
        <h1>管理与审计</h1>
        <p>管理内部用户、账号状态与登录锁定，并追踪关键操作。</p>
      </div>
      <button v-if="auth.isAdmin" class="primary-button" @click="showUser = !showUser">＋ 新建用户</button>
    </header>
    <p v-if="error" class="form-error">{{ error }}</p>
    <form v-if="showUser" class="panel compact-form" @submit.prevent="createUser">
      <label>用户名<input v-model="form.username" pattern="[a-zA-Z0-9_.-]{2,64}" required /></label>
      <label>姓名<input v-model="form.display_name" required /></label>
      <label>初始密码<input v-model="form.password" type="password" minlength="12" required /></label>
      <label>
        角色
        <select v-model="form.role">
          <option value="viewer">只读用户</option>
          <option value="engineer">售后工程师</option>
          <option value="reviewer">知识审核员</option>
          <option value="admin">管理员</option>
        </select>
      </label>
      <button class="primary-button">创建</button>
    </form>
    <section v-if="auth.isAdmin" class="panel table-panel admin-users">
      <div class="panel-heading">
        <div><p class="eyebrow">USERS</p><h2>内部用户</h2></div>
      </div>
      <div class="simple-table">
        <div v-for="user in users" :key="user.id">
          <span class="avatar small">{{ user.display_name.slice(0, 1) }}</span>
          <span><strong>{{ user.display_name }}</strong><small>{{ user.username }}</small></span>
          <span>{{ user.role }}</span>
          <span><b :class="user.active ? 'ok' : 'warn'">{{ user.active ? '启用' : '停用' }}</b><small v-if="isLocked(user)" class="warn">登录已锁定</small></span>
          <small>{{ user.last_login_at ? `最近登录 ${new Date(user.last_login_at).toLocaleString()}` : '尚未登录' }}</small>
          <span class="user-actions">
            <button v-if="isLocked(user)" class="secondary-button" :disabled="busyUserId === user.id" @click="unlock(user)">解锁</button>
            <button
              class="secondary-button"
              :class="{ danger: user.active }"
              :disabled="busyUserId === user.id || (user.id === auth.user?.id && user.active)"
              @click="changeStatus(user)"
            >{{ user.active ? '停用' : '启用' }}</button>
          </span>
        </div>
      </div>
    </section>
    <section class="panel table-panel">
      <div class="panel-heading"><div><p class="eyebrow">AUDIT TRAIL</p><h2>最近操作</h2></div></div>
      <div class="audit-list">
        <div v-for="log in logs" :key="log.id">
          <span class="audit-dot"></span>
          <div><strong>{{ log.action }}</strong><small>{{ log.username }} · {{ log.target_type }} {{ log.target_id || '' }}</small></div>
          <time>{{ new Date(log.created_at).toLocaleString() }}</time>
        </div>
      </div>
    </section>
  </div>
</template>
