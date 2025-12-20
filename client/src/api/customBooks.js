import axios from 'axios'

// DEV: Vite proxy (/api -> 127.0.0.1:5000)
// PROD: allow overriding via VITE_API_BASE
const API_BASE = import.meta.env.VITE_API_BASE || ''
const API_URL = import.meta.env.DEV ? '/api/custom-books' : `${API_BASE}/api/custom-books`

const api = axios.create({
  baseURL: API_URL
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

export const customBooksAPI = {
  create(formData) {
    return api.post('/', formData)
  },

  get(customId) {
    return api.get(`/${customId}`)
  }
}
