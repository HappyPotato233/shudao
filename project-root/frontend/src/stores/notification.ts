import { defineStore } from 'pinia'
import { ref } from 'vue'
import { notificationApi } from '@/api'

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)

  async function fetchUnreadCount() {
    try {
      const res = await notificationApi.unreadCount()
      unreadCount.value = res?.total || 0
    } catch {
      unreadCount.value = 0
    }
  }

  function setUnreadCount(count: number) {
    unreadCount.value = count
  }

  function decrementUnread(delta = 1) {
    unreadCount.value = Math.max(0, unreadCount.value - delta)
  }

  function reset() {
    unreadCount.value = 0
  }

  return { unreadCount, fetchUnreadCount, setUnreadCount, decrementUnread, reset }
})
