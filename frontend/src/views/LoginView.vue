<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../services/api'

const auth = useAuthStore()
const router = useRouter()
const username = ref('admin')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    await router.push('/')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-story">
      <div class="login-brand"><span>机</span> 机床售后技术支持工作台</div>
      <div class="story-copy">
        <p class="eyebrow light">AFTER-SALES KNOWLEDGE OPERATIONS</p>
        <h1>让每一次维修判断，<br />都有依据可循。</h1>
        <p>把分散的产品资料、报警路径、备件信息和维修经验，沉淀为可审核、可追溯的企业知识。</p>
      </div>
      <div class="story-points">
        <span>来源可追溯</span><span>版本可控制</span><span>工程师最终确认</span>
      </div>
    </section>
    <section class="login-panel">
      <form class="login-card" @submit.prevent="submit">
        <div>
          <p class="eyebrow">SECURE WORKSPACE</p>
          <h2>登录企业工作台</h2>
          <p class="muted">请输入企业分配的账号和密码。首次登录后请及时修改初始密码。</p>
        </div>
        <label>用户名<input v-model="username" autocomplete="username" required /></label>
        <label>密码<input v-model="password" type="password" autocomplete="current-password" required /></label>
        <p v-if="error" class="form-error">{{ error }}</p>
        <button class="primary-button full" :disabled="loading">{{ loading ? '正在验证…' : '进入工作台' }}</button>
        <div class="safety-line"><span>◈</span> 系统仅提供辅助建议，不执行机床控制</div>
      </form>
    </section>
  </div>
</template>
