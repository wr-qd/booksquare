import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const API_URL = import.meta.env.DEV ? '/api/reader' : `${API_BASE}/api/reader`

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

export const readerAPI = {
  sources(bookId) {
    return api.get('/sources', { params: { book_id: bookId } })
  },
  download(payload) {
    return api.post('/download', payload)
  },
  upload({ bookId, file, title, author, format }) {
    const form = new FormData()
    form.append('book_id', bookId)
    form.append('file', file)
    if (title) form.append('title', title)
    if (author) form.append('author', author)
    if (format) form.append('format', format)
    return api.post('/upload', form, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  assets(bookId) {
    return api.get('/assets', { params: { book_id: bookId } })
  },
  progress(assetId) {
    return api.get(`/assets/${assetId}/progress`)
  },
  setProgress(assetId, payload) {
    return api.post(`/assets/${assetId}/progress`, payload)
  },
  assetMeta(assetId) {
    return api.get(`/assets/${assetId}/meta`)
  },
  assetText(assetId) {
    return api.get(`/assets/${assetId}/file`, { responseType: 'text' })
  },
  assetBinary(assetId) {
    return api.get(`/assets/${assetId}/file`, { responseType: 'arraybuffer' })
  }
}
