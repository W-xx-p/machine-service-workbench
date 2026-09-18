import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../services/api'
import { AUTH_TOKEN_KEY, AUTH_USER_KEY } from '../constants'

export interface User {
  id: number
  username: string
  display_name: string
  role: 'viewer' | 'engineer' | 'reviewer' | 'admin'
  active: boolean
}

function readSavedUser(): User | null {
  const saved = localStorage.getItem(AUTH_USER_KEY)
  if (!saved) return null
  try {
    const parsed = JSON.parse(saved) as User
    if (!parsed?.username || !['viewer', 'engineer', 'reviewer', 'admin'].includes(parsed.role)) {
      throw new Error('invalid cached user')
    }
    return parsed
  } catch {
    localStorage.removeItem(AUTH_USER_KEY)
    localStorage.removeItem(AUTH_TOKEN_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(readSavedUser())
  const isLoggedIn = computed(() => Boolean(user.value && localStorage.getItem(AUTH_TOKEN_KEY)))
  const canReview = computed(() => ['reviewer', 'admin'].includes(user.value?.role || ''))
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username: string, password: string) {
    const { data } = await api.post('/auth/login', { username, password })
    localStorage.setItem(AUTH_TOKEN_KEY, data.access_token)
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(data.user))
    user.value = data.user
  }

  function logout() {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    localStorage.removeItem(AUTH_USER_KEY)
    user.value = null
  }

  return { user, isLoggedIn, canReview, isAdmin, login, logout }
})
