<template>
  <div class="profile-page">
    <div class="profile-inner">
      <h1 class="page-title">个人中心</h1>

      <div class="profile-card">
        <div class="profile-avatar">{{ store.initial }}</div>
        <div class="profile-info">
          <div class="profile-name">{{ store.displayName }}</div>
          <div class="profile-role">{{ roleLabel }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">个人信息</div>
        <el-form label-width="90px" size="default" style="max-width: 480px">
          <el-form-item label="用户名">
            <el-input :model-value="store.user?.username" disabled />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input :model-value="store.user?.real_name" disabled />
          </el-form-item>
          <el-form-item label="部门">
            <el-input :model-value="store.user?.department || '—'" disabled />
          </el-form-item>
        </el-form>
      </div>

      <div class="card">
        <div class="card-title">修改密码</div>
        <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px" style="max-width: 480px">
          <el-form-item label="原密码" prop="oldPassword">
            <el-input v-model="pwdForm.oldPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码" prop="newPassword">
            <el-input v-model="pwdForm.newPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input v-model="pwdForm.confirmPassword" type="password" show-password />
          </el-form-item>
          <el-button type="primary" @click="onChangePassword">保存修改</el-button>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

const store = useUserStore()
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const roleLabel = computed(() => {
  const map: Record<string, string> = {
    admin: '管理员',
    user: '普通用户',
  }
  return map[store.role as string] || '未知'
})

const pwdRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    {
      validator: (_r, v, cb) => {
        if (v !== pwdForm.newPassword) cb(new Error('两次密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function onChangePassword() {
  await pwdFormRef.value?.validate()
  ElMessage.success('密码已修改')
  pwdForm.oldPassword = ''
  pwdForm.newPassword = ''
  pwdForm.confirmPassword = ''
}
</script>

<style scoped>
.profile-page {
  flex: 1;
  overflow: auto;
}
.profile-inner {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
}
.profile-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  margin-bottom: 16px;
}
.profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--primary-light);
  color: var(--primary);
  display: grid;
  place-items: center;
  font-size: 28px;
  font-weight: 600;
}
.profile-name {
  font-size: 18px;
  font-weight: 600;
}
.profile-role {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: 20px;
  margin-bottom: 16px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}
</style>
