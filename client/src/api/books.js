import axios from 'axios'

// DEV: use Vite proxy (/api -> 127.0.0.1:5000) to avoid CORS preflight issues.
// PROD: allow overriding via VITE_API_BASE if needed.
const API_BASE = import.meta.env.VITE_API_BASE || ''
const API_URL = import.meta.env.DEV ? '/api/books' : `${API_BASE}/api/books`

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

export const booksAPI = {
  search(q, limit = 50) {
    return api.get('/search', { params: { q, limit } })
  },

  doubanStatus() {
    return api.get('/douban/status')
  },

  doubanLogin(wait = false, timeout = 240) {
    return api.post('/douban/login', null, { params: { wait, timeout } })
  },

  doubanLogout() {
    return api.post('/douban/logout')
  },

  bilibiliSearch(q, limit = 5) {
    return api.get('/bilibili/search', { params: { q, limit } })
  },

  bilibiliArticle(id) {
    return api.get('/bilibili/article', { params: { id } })
  },

  bilibiliImage(url) {
    return api.get('/bilibili/image', { params: { url }, responseType: 'blob' })
  },

  weiboStatus() {
    return api.get('/weibo/status')
  },

  weiboLogin(wait = false, timeout = 240) {
    return api.post('/weibo/login', null, { params: { wait, timeout } })
  },

  weiboLogout() {
    return api.post('/weibo/logout')
  },

  weiboSearch(q, limit = 30) {
    return api.get('/weibo/search', { params: { q, limit } })
  },

  advancedSearch(payload) {
    return api.post('/advanced-search', payload)
  },

  // Default lower max to reduce Douban 403 when deep paging.
  detail(bookId, wcMaxComments = 80, previewComments = 20) {
    return api.get(`/${bookId}`, {
      params: { wc_max_comments: wcMaxComments, preview_comments: previewComments }
    })
  },

  basic(bookId) {
    return api.get(`/${bookId}/basic`)
  },

  wordcloud(bookId, wcMaxComments = 200) {
    return api.get(`/${bookId}/wordcloud`, { params: { wc_max_comments: wcMaxComments } })
  },

  comments(bookId, page = 1, limit = 20) {
    return api.get(`/${bookId}/comments`, { params: { page, limit } })
  }
}
