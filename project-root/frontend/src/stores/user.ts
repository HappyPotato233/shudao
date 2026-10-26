import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

export type UserRole = 'admin' | 'user'

export interface UserInfo {
  user_id: string
  username: string
  real_name: string
  role: UserRole
  department?: string
}

function normalizeRole(role: string): UserRole {
  const map: Record<string, UserRole> = {
    Admin: 'admin',
    User: 'user',
  }
  return map[role] || 'user'
}

function normalizeUser(raw: any): UserInfo {
  return {
    user_id: raw.id || raw.user_id || '',
    username: raw.username || '',
    real_name: raw.name || raw.real_name || raw.username || '',
    role: normalizeRole(raw.role || 'User'),
    department: raw.department || '',
  }
}

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null)
  const token = ref(localStorage.getItem('access_token') || '')

  const isLoggedIn = computed(() => !!token.value)
  const role = computed(() => user.value?.role)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.real_name || user.value?.username || '')
  const initial = computed(() => displayName.value.charAt(0) || '蜀')

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('refresh_token', res.refresh_token)
    if (res.user) user.value = normalizeUser(res.user)
    else await fetchMe()
  }

  async function fetchMe() {
    if (!token.value) return
    const raw = await authApi.me()
    user.value = normalizeUser(raw)
  }

  function logout() {
    user.value = null
    token.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  return { user, token, isLoggedIn, role, isAdmin, displayName, initial, login, fetchMe, logout }
})
