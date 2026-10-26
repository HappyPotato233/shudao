<template>
  <div class="user-page">
    <div class="user-inner">
      <div class="page-head">
        <h1 class="page-title">用户管理</h1>
        <el-button type="primary" :icon="Plus" @click="onCreate">新增用户</el-button>
      </div>

      <div class="card">
        <el-table v-loading="loading" :data="users" stripe style="width: 100%">
          <el-table-column prop="username" label="用户名" min-width="120" />
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column label="角色" min-width="140">
            <template #default="{ row }">
              <el-select
                :model-value="row.role"
                size="small"
                style="width: 120px"
                @change="(v: string) => onChangeRole(row, v)"
              >
                <el-option label="管理员" value="Admin" />
                <el-option label="普通用户" value="User" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column prop="department" label="部门" min-width="120" />
          <el-table-column prop="project" label="项目" min-width="120" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                text
                :type="row.is_active ? 'danger' : 'success'"
                @click="onToggleActive(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-button size="small" text type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="editing" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="管理员" value="Admin" />
            <el-option label="普通用户" value="User" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="form.department" />
        </el-form-item>
        <el-form-item label="项目" prop="project">
          <el-input v-model="form.project" />
        </el-form-item>
        <el-form-item v-if="!editing" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位，含大小写+数字+特殊字符" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { userApi } from '@/api'

const users = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref(false)
const editingId = ref('')
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  name: '',
  role: 'User',
  department: '',
  project: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  department: [{ required: true, message: '请输入部门', trigger: 'blur' }],
  project: [{ required: true, message: '请输入项目', trigger: 'blur' }],
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await userApi.list({ page: 1, page_size: 100 })
    users.value = res?.items || []
  } catch (e: any) {
    ElMessage.warning('用户列表加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function onCreate() {
  editing.value = false
  editingId.value = ''
  Object.assign(form, { username: '', name: '', role: 'User', department: '', project: '', password: '' })
  dialogVisible.value = true
}

function onEdit(row: any) {
  editing.value = true
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    name: row.name,
    role: row.role,
    department: row.department,
    project: row.project,
    password: '',
  })
  dialogVisible.value = true
}

async function onChangeRole(row: any, role: string) {
  try {
    await userApi.update(row.id, { role })
    row.role = role
    ElMessage.success('角色已更新')
  } catch {
    ElMessage.warning('角色更新失败，请稍后重试')
  }
}

async function onToggleActive(row: any) {
  const action = row.is_active ? '禁用' : '启用'
  try {
    await userApi.update(row.id, { is_active: !row.is_active })
    row.is_active = !row.is_active
    ElMessage.success(`已${action}`)
  } catch {
    ElMessage.warning(`${action}失败，请稍后重试`)
  }
}

async function onDelete(row: any) {
  await ElMessageBox.confirm(`确认删除用户「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await userApi.delete(row.id)
    users.value = users.value.filter((u) => u.id !== row.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.warning('删除失败，请稍后重试')
  }
}

async function onSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editing.value) {
      const data: any = {
        name: form.name,
        role: form.role,
        department: form.department,
        project: form.project,
      }
      await userApi.update(editingId.value, data)
      ElMessage.success('已更新')
    } else {
      await userApi.create({ ...form })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadUsers()
  } catch {
    ElMessage.warning('保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.user-page {
  flex: 1;
  overflow: auto;
}
.user-inner {
  max-width: 1000px;
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
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 16px;
}
</style>
