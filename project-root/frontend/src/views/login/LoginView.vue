<template>
  <div class="login-page">
    <div class="login-card">
      <!-- 渐变品牌头部 -->
      <header class="card-header">
        <div class="header-top">
          <span class="brand-icon">蜀</span>
          <span class="status-pill">
            <span class="status-dot" aria-hidden="true"></span>
            <span class="status-text">安全运行中</span>
          </span>
        </div>
        <div class="brand-block">
          <h1 class="brand-name">蜀道安全助手</h1>
          <p class="brand-sub">工程建设安全生产一体化平台</p>
        </div>
      </header>

      <!-- 白底表单区 -->
      <div class="card-body">
        <div class="tab-switch" role="tablist" aria-label="登录与注册">
          <button
            type="button"
            role="tab"
            class="tab-item"
            :class="{ 'is-active': tab === 'login' }"
            :aria-selected="tab === 'login'"
            @click="tab = 'login'"
          >
            登录
          </button>
          <button
            type="button"
            role="tab"
            class="tab-item"
            :class="{ 'is-active': tab === 'register' }"
            :aria-selected="tab === 'register'"
            @click="tab = 'register'"
          >
            注册
          </button>
        </div>

        <!-- 登录表单 -->
        <el-form
          v-show="tab === 'login'"
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          size="large"
          class="auth-form"
          @submit.prevent
        >
          <div class="field">
            <div class="field-head">
              <span class="field-label">用户名 / 工号</span>
              <span class="field-tag">SEC-ID</span>
            </div>
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="请输入用户名 / 工号" :prefix-icon="User" />
            </el-form-item>
          </div>

          <div class="field">
            <div class="field-head">
              <span class="field-label">密码</span>
              <span class="field-tag">KEY PASS</span>
            </div>
            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="onLogin"
              />
            </el-form-item>
          </div>

          <div class="form-options">
            <label class="remember">
              <input class="remember-box" type="checkbox" checked />
              <span class="remember-text">记住登录状态</span>
            </label>
            <span class="forgot" title="请联系平台管理员重置密码">忘记密码？</span>
          </div>

          <el-button type="primary" size="large" :loading="loading" class="submit-btn" @click="onLogin">
            登录系统
            <span class="submit-arrow" aria-hidden="true">→</span>
          </el-button>
        </el-form>

        <!-- 注册表单 -->
        <el-form
          v-show="tab === 'register'"
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          size="large"
          class="auth-form"
          @submit.prevent
        >
          <div class="field">
            <div class="field-head">
              <span class="field-label">用户名</span>
              <span class="field-tag">ACC-ID</span>
            </div>
            <el-form-item prop="username">
              <el-input v-model="registerForm.username" placeholder="请输入用户名" :prefix-icon="User" />
            </el-form-item>
          </div>

          <div class="field">
            <div class="field-head">
              <span class="field-label">姓名</span>
              <span class="field-tag">REAL NAME</span>
            </div>
            <el-form-item prop="realName">
              <el-input v-model="registerForm.realName" placeholder="请输入姓名" :prefix-icon="Postcard" />
            </el-form-item>
          </div>

          <div class="field">
            <div class="field-head">
              <span class="field-label">密码</span>
              <span class="field-tag">KEY PASS</span>
            </div>
            <el-form-item prop="password">
              <el-input
                v-model="registerForm.password"
                type="password"
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>
          </div>

          <div class="field">
            <div class="field-head">
              <span class="field-label">确认密码</span>
              <span class="field-tag">CONFIRM</span>
            </div>
            <el-form-item prop="confirmPassword">
              <el-input
                v-model="registerForm.confirmPassword"
                type="password"
                placeholder="请再次输入密码"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>
          </div>

          <el-button type="primary" size="large" :loading="loading" class="submit-btn" @click="onRegister">
            注册账号
            <span class="submit-arrow" aria-hidden="true">→</span>
          </el-button>
        </el-form>
      </div>

      <!-- 安全合规说明 -->
      <footer class="card-footer">
        <span class="footer-line">
          <span class="footer-check" aria-hidden="true">✓</span>
          国资委安全合规标准 GB/T 33000 认证
        </span>
        <span class="footer-line footer-line--dim">AUTHORIZED ACCESS ONLY</span>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Postcard } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const store = useUserStore()
const route = useRoute()
const router = useRouter()

const tab = ref('login')
const loading = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', realName: '', password: '', confirmPassword: '' })

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  realName: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    {
      validator: (_rule, value, callback) => {
        if (value !== registerForm.password) callback(new Error('两次密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function onLogin() {
  await loginFormRef.value?.validate()
  loading.value = true
  try {
    await store.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/dashboard')
  } catch {
    // 错误提示已由 http 拦截器统一处理，这里不再重复提示
  } finally {
    loading.value = false
  }
}

async function onRegister() {
  await registerFormRef.value?.validate()
  loading.value = true
  try {
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
  } catch {
    // 错误提示已由 http 拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 全屏登录页：浅灰底 + 极淡网格纹理 */
.login-page {
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  align-items: safe center;
  justify-content: center;
  padding: 24px 16px;
  overflow-y: auto;
  background-color: var(--color-bg);
  background-image:
    linear-gradient(rgba(20, 23, 26, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(20, 23, 26, 0.045) 1px, transparent 1px);
  background-size: 28px 28px;
}
.login-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 45%, rgba(247, 249, 251, 0) 28%, var(--color-bg) 76%);
  pointer-events: none;
}

/* 卡片：2px 黑描边 + 4px 硬阴影 + 8px 圆角 */
.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
  background: #ffffff;
  border: 2px solid #000000;
  border-radius: 8px;
  box-shadow: 4px 4px 0 #000000;
  overflow: hidden;
}

/* 品牌头部：唯一使用品牌渐变的位置之一 */
.card-header {
  background: var(--gradient-brand);
  border-bottom: 2px solid #000000;
  padding: 20px;
  color: #ffffff;
}

.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.brand-icon {
  width: 42px;
  height: 42px;
  flex: none;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #000000;
  box-shadow: 2px 2px 0 #000000;
  color: var(--primary);
  font-family: var(--font-headline);
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
  user-select: none;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  border: 2px solid #000000;
  backdrop-filter: blur(4px);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  animation: status-pulse 1.8s ease-in-out infinite;
}

.status-text {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.08em;
  line-height: 1.4;
  color: #ffffff;
  white-space: nowrap;
}

@keyframes status-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.82);
  }
}

.brand-block {
  margin-top: 14px;
}

.brand-name {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.01em;
  color: #ffffff;
}

.brand-sub {
  margin: 4px 0 0;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.04em;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.85);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
  background: #ffffff;
}

/* 页签：底部细线 + 激活紫色粗下划线 */
.tab-switch {
  display: flex;
  border-bottom: 2px solid var(--divider);
}

.tab-item {
  position: relative;
  flex: 1;
  padding: 0 0 10px;
  border: none;
  background: none;
  cursor: pointer;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 500;
  color: var(--text-tertiary);
  transition: color 0.2s ease;
}

.tab-item::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 3px;
  background: transparent;
  transition: background 0.2s ease;
}

.tab-item:hover {
  color: var(--text-primary);
}

.tab-item.is-active {
  color: var(--text-primary);
  font-weight: 700;
}

.tab-item.is-active::after {
  background: var(--accent);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary);
}

.field-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.auth-form :deep(.el-form-item__error) {
  position: static;
  width: 100%;
  padding-top: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.4;
  color: var(--danger);
}

/* 输入框：白底 + 2px 黑描边 + 4px 圆角，聚焦时蓝色硬阴影 */
.auth-form :deep(.el-input__wrapper) {
  min-height: 42px;
  padding: 2px 12px;
  border-radius: 4px;
  background: #ffffff;
  box-shadow: 0 0 0 2px #000000 inset;
  transition: all 0.2s ease;
}

.auth-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 2px var(--text-primary) inset;
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 2px #000000 inset,
    3px 3px 0 var(--primary);
}

.auth-form :deep(.el-input__inner) {
  height: 36px;
  font-size: 14px;
  color: var(--text-primary);
}

.auth-form :deep(.el-input__inner::placeholder) {
  color: var(--text-tertiary);
}

.auth-form :deep(.el-input__prefix) {
  color: var(--text-tertiary);
}

.auth-form :deep(.el-input__prefix .el-icon) {
  font-size: 17px;
}

.auth-form :deep(.el-input__suffix) {
  color: var(--text-tertiary);
}

.auth-form :deep(.el-input__password:hover) {
  color: var(--text-primary);
}

/* 记住登录 + 忘记密码 */
.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 2px;
}

.remember {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.remember-box {
  appearance: none;
  -webkit-appearance: none;
  position: relative;
  flex: none;
  width: 16px;
  height: 16px;
  margin: 0;
  border: 2px solid #000000;
  border-radius: 4px;
  background: #ffffff;
  box-shadow: 1px 1px 0 #000000;
  cursor: pointer;
}

.remember-box:checked {
  background: var(--primary);
}

.remember-box:checked::after {
  content: "";
  position: absolute;
  left: 4px;
  top: 1px;
  width: 4px;
  height: 8px;
  border: solid #ffffff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.remember-box:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.remember-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.forgot {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  cursor: default;
}

/* 主按钮：品牌渐变 + 黑描边 + 4px 硬阴影，仅用于登录/注册提交 */
.submit-btn {
  width: 100%;
  height: 44px;
  margin-top: 4px;
  border-radius: 4px;
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #ffffff;
}

.submit-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.submit-arrow {
  font-family: var(--font-mono);
  font-size: 15px;
  line-height: 1;
}

.submit-btn:hover {
  transform: translate(-1px, -1px);
  box-shadow: 4px 4px 0 #000000;
}

.submit-btn:active {
  transform: translate(2px, 2px);
  box-shadow: none;
}

/* 底部合规说明 */
.card-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 12px 16px;
  background: var(--color-bg);
  border-top: 2px solid #000000;
  text-align: center;
}

.footer-line {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.4;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.footer-check {
  color: var(--success-text);
  font-size: 11px;
  font-weight: 700;
}

.footer-line--dim {
  font-size: 9px;
  letter-spacing: 0.12em;
  color: var(--text-tertiary);
}

@media (max-width: 420px) {
  .login-page {
    padding: 16px 12px;
  }

  .card-header {
    padding: 18px;
  }

  .card-body {
    padding: 20px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot {
    animation: none;
  }
}
</style>
