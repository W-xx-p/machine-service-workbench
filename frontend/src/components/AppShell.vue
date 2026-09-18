<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api, errorMessage } from '../services/api'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const menuOpen = ref(false)
const passwordOpen = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const passwordError = ref('')
const passwordSaving = ref(false)

const items = computed(() => [
  { to: '/', label: '运营总览', icon: '⌂' },
  { to: '/ask', label: '故障辅助', icon: '◇' },
  { to: '/products', label: '产品档案', icon: '▦' },
  { to: '/service-data', label: '报警与备件', icon: '⊕' },
  { to: '/documents', label: '文档中心', icon: '▤' },
  { to: '/knowledge', label: '知识审核', icon: '✓' },
  { to: '/cases', label: '维修案例', icon: '◫' },
  ...(auth.canReview ? [{ to: '/admin', label: '管理与审计', icon: '⚙' }] : []),
])

function logout() {
  auth.logout()
  router.push('/login')
}

async function changePassword() {
  passwordError.value = ''
  passwordSaving.value = true
  try {
    await api.post('/auth/change-password', {
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    passwordOpen.value = false
    currentPassword.value = ''
    newPassword.value = ''
    logout()
  } catch (err) {
    passwordError.value = errorMessage(err)
  } finally {
    passwordSaving.value = false
  }
}
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ open: menuOpen }">
      <div class="brand">
        <div class="brand-mark">机</div>
        <div><strong>机床售后技术支持工作台</strong><small>TECH SUPPORT</small></div>
      </div>
      <nav>
        <RouterLink
          v-for="item in items"
          :key="item.to"
          :to="item.to"
          :class="{ active: route.path === item.to }"
          @click="menuOpen = false"
        >
          <span class="nav-icon">{{ item.icon }}</span>{{ item.label }}
        </RouterLink>
      </nav>
      <div class="sidebar-note">
        <span class="pulse"></span>
        <div><strong>工程师确认模式</strong><small>系统不执行机床控制</small></div>
      </div>
      <div class="user-card">
        <div class="avatar">{{ auth.user?.display_name.slice(0, 1) }}</div>
        <div><strong>{{ auth.user?.display_name }}</strong><small>{{ auth.user?.role }}</small></div>
        <button class="icon-button" title="修改密码" @click="passwordOpen = true">⌘</button>
        <button class="icon-button" title="退出" @click="logout">↗</button>
      </div>
    </aside>
    <main class="main-content">
      <header class="mobile-header">
        <button class="icon-button" @click="menuOpen = !menuOpen">☰</button>
        <strong>机床售后技术支持工作台</strong>
        <span></span>
      </header>
      <RouterView />
    </main>
    <div v-if="menuOpen" class="overlay" @click="menuOpen = false"></div>
    <div v-if="passwordOpen" class="modal-backdrop" @click.self="passwordOpen = false">
      <form class="password-modal" @submit.prevent="changePassword">
        <div class="panel-heading"><div><p class="eyebrow">ACCOUNT SECURITY</p><h2>修改密码</h2></div><button type="button" class="icon-button" @click="passwordOpen = false">×</button></div>
        <label>当前密码<input v-model="currentPassword" type="password" autocomplete="current-password" required minlength="8" /></label>
        <label>新密码<input v-model="newPassword" type="password" autocomplete="new-password" required minlength="12" /><small>至少 12 个字符</small></label>
        <p v-if="passwordError" class="form-error">{{ passwordError }}</p>
        <button class="primary-button full" :disabled="passwordSaving">{{ passwordSaving ? '正在修改…' : '修改并重新登录' }}</button>
      </form>
    </div>
  </div>
</template>
