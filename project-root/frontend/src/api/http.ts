import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

export interface ApiResult<T = unknown> {
  code: number
  message: string
  data: T
}

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截：自动附加 access token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一错误码处理
http.interceptors.response.use(
  (response: AxiosResponse<ApiResult>) => {
    const { code, message, data } = response.data
    if (code === 0) return data as any

    // 40103 触发 refresh 轮换
    if (code === 40103) {
      return refreshAndRetry(response.config)
    }

    // 40303 角色无权限：静默 reject，由页面局部处理，不全局弹窗
    if (code === 40303) {
      return Promise.reject(new Error(message || '无权限'))
    }

    // 40100 空闲超时，清理会话跳登录
    if (code === 40100) {
      clearSession()
      router.push('/login')
      ElMessage.warning('登录已过期，请重新登录')
      return Promise.reject(new Error(message))
    }

    ElMessage.error(message || '请求失败')
    return Promise.reject(new Error(message))
  },
  (error) => {
    const status = error.response?.status
    const code = error.response?.data?.code
    const message = error.response?.data?.message

    if (status === 401) {
      // 区分三种 401 业务场景，屏蔽原始英文报错
      if (code === 40102) {
        ElMessage.error('该用户账号已被禁用，禁止登录')
      } else if (code === 40101) {
        ElMessage.error('用户名或密码错误')
      } else {
        clearSession()
        router.push('/login')
        ElMessage.warning('登录已过期，请重新登录')
      }
    } else if (status === 403 && code === 40303) {
      // 权限不足：静默 reject，页面局部展示空态，不全局弹窗
    } else if (code === 40001) {
      // 参数校验失败：登录场景下对用户更友好地提示账号或密码错误
      ElMessage.error('账号或密码输入有误，请检查后重试')
    } else {
      ElMessage.error(message || '网络异常，请稍后重试')
    }
    return Promise.reject(error)
  },
)

async function refreshAndRetry(config: AxiosRequestConfig) {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    clearSession()
    router.push('/login')
    return Promise.reject(new Error('登录已过期'))
  }

  try {
    const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
    const { access_token, refresh_token } = res.data.data
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    config.headers!.Authorization = `Bearer ${access_token}`
    return http(config)
  } catch {
    clearSession()
    router.push('/login')
    return Promise.reject(new Error('登录已过期'))
  }
}

function clearSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

// 拦截器已把 AxiosResponse 解包为 data，这里做类型适配：
// 所有请求方法返回 Promise<any>，业务层自行断言具体类型
export default http as unknown as {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
}
