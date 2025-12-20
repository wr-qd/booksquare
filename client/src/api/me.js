import axios from 'axios'

// DEV: use Vite proxy (/api -> 127.0.0.1:5000) to avoid CORS preflight issues.
// PROD: allow overriding via VITE_API_BASE if frontend/backend are on different origins.
const API_BASE = import.meta.env.VITE_API_BASE || ''
const API_URL = import.meta.env.DEV ? '/api/me' : `${API_BASE}/api/me`

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

export const meAPI = {
  listBookshelf() {
    return api.get('/bookshelf')
  },

  getBookshelfStatus(bookId) {
    return api.get(`/bookshelf/${bookId}`)
  },

  likeBook(payload) {
    return api.post('/bookshelf', payload)
  },

  unlikeBook(bookId) {
    return api.delete(`/bookshelf/${bookId}`)
  },

  listReadingLogs(limit = 50) {
    return api.get('/reading-logs', { params: { limit } })
  },

  listBookReadingLogs(bookId) {
    return api.get(`/reading-logs/${bookId}`)
  },

  createReadingLog(payload) {
    return api.post('/reading-logs', payload)
  },

  deleteReadingLog(logId) {
    return api.delete(`/reading-logs/${logId}`)
  },

  listNotes(bookId) {
    // Prefer the query-based endpoint; if some deployments lack it, fallback to path variant.
    return api.get('/notes', { params: { book_id: bookId } }).catch((err) => {
      if (err?.response?.status === 404 && bookId) {
        return api.get(`/notes/${bookId}`)
      }
      throw err
    })
  },

  createNote(payload) {
    return api.post('/notes', payload)
  },

  deleteNote(noteId) {
    return api.delete(`/notes/${noteId}`)
  }
}
