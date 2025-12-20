import axios from 'axios'

// DEV: use Vite proxy (/api -> 127.0.0.1:5000)
// PROD: allow overriding via VITE_API_BASE
const API_BASE = import.meta.env.VITE_API_BASE || ''
const API_URL = import.meta.env.DEV ? '/api/recommendations' : `${API_BASE}/api/recommendations`

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

export const recommendationsAPI = {
  today() {
    return api.get('/today')
  },
  refresh() {
    return api.post('/refresh')
  }
}
