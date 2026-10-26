<template>
  <div class="notification-page">
    <div class="notification-inner">
      <div class="page-head">
        <h1 class="page-title">消息通知</h1>
        <div class="head-actions">
          <el-button v-if="store.isAdmin" type="primary" :icon="Promotion" @click="openSendDialog">
            发送消息
          </el-button>
          <el-button size="small" @click="onMarkAllRead">全部已读</el-button>
          <el-button size="small" type="danger" plain @click="onClearRead">清空已读</el-button>
        </div>
      </div>

      <el-tabs v-model="tab">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="未读" name="unread" />
        <el-tab-pane label="隐患类" name="hazard" />
        <el-tab-pane v-if="store.isAdmin" label="已发送" name="sent" />
      </el-tabs>

      <div v-if="tab === 'sent' && store.isAdmin" class="notification-list">
        <el-empty v-if="!sentList.length" description="暂无发送记录" :image-size="80" />
        <div v-for="item in sentList" :key="item.notification_id" class="notification-item">
          <span class="tag tag-neutral">已发送</span>
          <div class="item-body">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-content">{{ item.content }}</div>
          </div>
          <span class="item-time">{{ item.created_at }}</span>
        </div>
      </div>

      <div v-else class="notification-list">
        <el-empty v-if="!filteredList.length" description="暂无消息" :image-size="80" />
        <div
          v-for="item in filteredList"
          :key="item.notification_id"
          class="notification-item"
          :class="{ unread: !item.is_read }"
          @click="onRead(item)"
        >
          <span class="tag" :class="categoryClass(item.type)">{{ categoryLabel(item.type) }}</span>
          <div class="item-body">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-content">{{ item.content }}</div>
          </div>
          <span class="item-time">{{ (item.created_at || '').slice(0, 16) }}</span>
          <el-button size="small" text type="danger" :icon="Delete" @click.stop="onDelete(item)" />
        </div>
      </div>
    </div>

    <!-- 管理员发送消息弹窗 -->
    <el-dialog v-model="sendDialogVisible" title="发送消息" width="520px" append-to-body>
      <el-form ref="sendFormRef" :model="sendForm" :rules="sendRules" label-width="80px">
        <el-form-item label="目标用户" prop="user_ids">
          <el-select v-model="sendForm.user_ids" multiple filterable placeholder="选择接收用户" style="width: 100%">
            <el-option
              v-for="u in targetUsers"
              :key="u.id"
              :label="`${u.name}（${u.username}）`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="sendForm.title" placeholder="请输入消息标题" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="sendForm.content" type="textarea" :rows="4" placeholder="请输入消息内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sendDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sending" @click="onSendMessage">发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Promotion } from '@element-plus/icons-vue'
import { notificationApi, userApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'

const store = useUserStore()
const notificationStore = useNotificationStore()
const tab = ref('all')
const list = ref<any[]>([])
const sentList = ref<any[]>([])
const targetUsers = ref<any[]>([])

const sendDialogVisible = ref(false)
const sending = ref(false)
const sendFormRef = ref<FormInstance>()
const sendForm = reactive({ user_ids: [] as string[], title: '', content: '' })

const sendRules: FormRules = {
  user_ids: [{ required: true, type: 'array', min: 1, message: '请选择目标用户', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

const filteredList = computed(() => {
  if (tab.value === 'unread') return list.value.filter((i) => !i.is_read)
  if (tab.value === 'hazard') return list.value.filter((i) => isHazardType(i.type))
  return list.value
})

const HAZARD_TYPES = ['hazard_assigned', 'rectification_submitted', 'review_result', 'rectification_urge']

function isHazardType(t: string) {
  return HAZARD_TYPES.includes(t)
}

function categoryLabel(t: string) {
  if (isHazardType(t)) return '隐患类'
  return '系统'
}

function categoryClass(t: string) {
  if (isHazardType(t)) return 'tag-danger'
  return 'tag-neutral'
}

async function loadNotifications() {
  try {
    const res = await notificationApi.list({ page: 1, page_size: 50, read_status: 'all' })
    list.value = res?.items || []
  } catch (e: any) {
    ElMessage.warning('消息加载失败，请稍后重试')
  }
}

async function onRead(item: any) {
  if (item.is_read) return
  try {
    await notificationApi.markRead(item.notification_id)
    item.is_read = true
    notificationStore.decrementUnread(1)
  } catch (e: any) {
    ElMessage.warning('标记已读失败')
  }
}

async function onDelete(item: any) {
  try {
    await notificationApi.delete(item.notification_id)
    if (!item.is_read) notificationStore.decrementUnread(1)
    list.value = list.value.filter((i) => i.notification_id !== item.notification_id)
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.warning('删除失败')
  }
}

async function onMarkAllRead() {
  try {
    await notificationApi.readAll()
    list.value.forEach((i) => (i.is_read = true))
    notificationStore.setUnreadCount(0)
    ElMessage.success('已全部标记为已读')
  } catch (e: any) {
    ElMessage.warning('操作失败')
  }
}

async function onClearRead() {
  const readIds = list.value.filter((i) => i.is_read).map((i) => i.notification_id)
  if (!readIds.length) return
  try {
    await notificationApi.batchDelete(readIds)
    list.value = list.value.filter((i) => !i.is_read)
    notificationStore.setUnreadCount(list.value.filter((i) => !i.is_read).length)
    ElMessage.success('已清空已读')
  } catch (e: any) {
    ElMessage.warning('操作失败')
  }
}

async function openSendDialog() {
  sendDialogVisible.value = true
  if (!targetUsers.value.length) {
    try {
      const res = await userApi.list({ page: 1, page_size: 100 })
      targetUsers.value = res?.items || []
    } catch (e: any) {
      ElMessage.warning('用户列表加载失败')
    }
  }
}

async function onSendMessage() {
  await sendFormRef.value?.validate()
  sending.value = true
  try {
    const res = await notificationApi.send({
      user_ids: sendForm.user_ids,
      title: sendForm.title,
      content: sendForm.content,
    })
    sentList.value = [...(res?.sent || []), ...sentList.value]
    ElMessage.success(`已发送 ${res?.count || 0} 条消息`)
    sendDialogVisible.value = false
    sendForm.user_ids = []
    sendForm.title = ''
    sendForm.content = ''
  } catch {
    ElMessage.warning('发送失败，请稍后重试')
  } finally {
    sending.value = false
  }
}

onMounted(loadNotifications)
</script>

<style scoped>
.notification-page {
  flex: 1;
  overflow: auto;
}
.notification-inner {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notification-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.notification-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  cursor: pointer;
  transition: background 0.2s;
}
.notification-item:hover {
  background: #F7F9FB;
}
.notification-item.unread {
  background: var(--primary-light);
  border-color: var(--primary-border);
}
.item-body {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 3px;
}
.item-content {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-time {
  font-size: 12px;
  color: var(--text-tertiary);
  flex: none;
}
.tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-tag);
  font-size: 12px;
  font-weight: 500;
  flex: none;
}
.tag-danger {
  background: var(--danger-light);
  color: var(--danger-text);
}
.tag-info {
  background: var(--info-light);
  color: var(--info-text);
}
.tag-neutral {
  background: var(--divider);
  color: var(--text-secondary);
}
</style>
