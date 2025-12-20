import axios from 'axios'

// DEV: use Vite proxy (/api -> 127.0.0.1:5000) to avoid CORS preflight issues.
// PROD: allow overriding via VITE_API_BASE if needed.
const API_BASE = import.meta.env.VITE_API_BASE || ''
const API_URL = import.meta.env.DEV ? '/api/auth' : `${API_BASE}/api/auth`

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

export const authAPI = {
  // 发送验证码
  sendVerificationCode(email) {
    return api.post('/send-verification-code', { email })
  },

  // 注册（已取消验证码）
  register(email, username, password) {
    return api.post('/register', {
      email,
      username,
      password
    })
  },

  // 登录
  login(email, password) {
    return api.post('/login', {
      email,
      password
    })
  },

  // 验证token
  verifyToken(token) {
    return api.post('/verify-token', { token })
  },

  // 获取用户信息
  getProfile() {
    return api.get('/profile')
  }
}
