<template>
  <div class="home-container">
    <header class="header">
      <div class="header-content">
        <div class="brand" role="banner" aria-label="雾林书札">
          <img class="brand-mark" src="../assets/brand-mark.svg" alt="" aria-hidden="true" />
          <div class="brand-text">
            <div class="brand-title">雾林书札</div>
            <div class="brand-sub">岁月静好 · 读书有光</div>
          </div>
        </div>
        <div class="header-actions">
          <a class="ext-link" href="https://wap.txt80.com/" target="_blank" rel="noreferrer">资源可获取处</a>

          <div class="user-menu">
          <div class="user-avatar" @click="showUserMenu = !showUserMenu">
            <span>{{ userInitial }}</span>
          </div>
          <div v-if="showUserMenu" class="dropdown-menu">
            <div class="user-info">
              <div class="username">{{ user.username }}</div>
              <div class="email">{{ user.email }}</div>
            </div>
            <div class="menu-divider"></div>
            <button type="button" @click.stop="goToBookshelf" class="menu-item">
              我的书架
            </button>
            <button type="button" @click.stop="goToProfile" class="menu-item">
              个人信息
            </button>
            <button type="button" @click.stop="logout" class="menu-item logout">
              退出登录
            </button>
          </div>
        </div>
        </div>
      </div>
    </header>

    <main class="main-content">
      <div class="search-section">
          <h2 class="welcome-text">在林雾里，遇见一本书</h2>

        <div class="search-modes" role="tablist" aria-label="搜索模式">
          <button type="button" class="mode" :class="{ active: mode === 'title' }" @click="mode = 'title'">
            书名
          </button>
          <button type="button" class="mode" :class="{ active: mode === 'author' }" @click="mode = 'author'">
            作者
          </button>
          <button type="button" class="mode" :class="{ active: mode === 'advanced' }" @click="mode = 'advanced'">
            高级搜索
          </button>
        </div>

        <div class="search-box">
          <template v-if="mode !== 'advanced'">
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="mode === 'author' ? '输入作者名搜索...' : '输入书名搜索...'"
              @keyup.enter="handleSearch"
            />
          </template>

          <template v-else>
            <div class="select-wrap">
              <select v-model="genre" class="select">
                <option value="">选择书籍类型</option>
                <option value="小说">小说</option>
                <option value="散文">散文</option>
                <option value="诗歌">诗歌</option>
                <option value="科幻">科幻</option>
                <option value="历史">历史</option>
                <option value="心理">心理</option>
                <option value="成长">成长</option>
              </select>
            </div>
            <input
              v-model="mood"
              type="text"
              placeholder="输入描述（系统会自动提取情绪词），例如：最近很焦虑想看治愈温暖的书"
              @keyup.enter="handleSearch"
            />
          </template>

          <button @click="handleSearch" class="search-btn">搜索</button>
        </div>

        <div class="douban-auth" aria-label="豆瓣登录状态">
          <div class="douban-status">
            <span class="label">豆瓣：</span>
            <span v-if="doubanStatus.logged_in" class="ok">已保存登录态（仍可能被风控）</span>
            <span v-else-if="doubanStatus.login_running" class="pending">登录中…</span>
            <span v-else class="bad">未登录/可能被风控</span>
            <span v-if="doubanStatus.last_error" class="err" :title="doubanStatus.last_error">
              （{{ doubanStatus.last_error }}）
            </span>
          </div>
          <div class="douban-actions">
            <button type="button" class="mini" @click="refreshDoubanStatus" :disabled="doubanBusy">
              刷新状态
            </button>
            <button type="button" class="mini primary" @click="triggerDoubanLogin" :disabled="doubanBusy">
              豆瓣登录
            </button>
            <button
              v-if="doubanStatus.logged_in"
              type="button"
              class="mini"
              @click="triggerDoubanLogout"
              :disabled="doubanBusy"
            >
              退出豆瓣
            </button>
          </div>
        </div>

        <div v-if="progressVisible" class="progress-wrap" aria-label="搜索进度">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <div class="progress-text">正在搜索… {{ progress }}%</div>
        </div>
      </div>

      <section v-if="books.length" class="results">
        <div class="results-header">
          <h3>搜索结果</h3>
          <div class="meta">
            <span v-if="loading">加载中...</span>
            <span v-else>共 {{ books.length }} 本</span>
          </div>
        </div>

        <div class="grid">
          <article
            v-for="b in books"
            :key="b.book_id"
            class="book-card"
            @click="goDetail(b.book_id)"
            role="button"
            tabindex="0"
          >
            <div class="cover">
              <img :src="coverSrc(b.cover_url)" :alt="b.title" />
            </div>
            <div class="info">
              <div class="title" :title="b.title">{{ b.title || '（无标题）' }}</div>
              <div class="author" :title="b.author">{{ b.author || '作者未知' }}</div>
              <div class="rating">
                <span class="score">{{ formatRating(b.rating) }}</span>
                <span class="hint">豆瓣评分</span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <div class="recommendations" aria-label="每日推荐">
        <h3>每日推荐</h3>
        <div class="rec-head">
          <div class="rec-meta">
            <span v-if="recLoading">生成中…</span>
            <span v-else>今日已推荐 {{ recCount }}/{{ recLimit }}</span>
          </div>
          <button type="button" class="rec-refresh" @click="refreshDaily" :disabled="recLoading || !canRefresh">
            刷新推荐
          </button>
        </div>

        <div v-if="recError" class="rec-state error">{{ recError }}</div>
        <div v-else-if="!dailyRecs.length" class="rec-state">暂无推荐（先去书架加几本书吧）</div>
        <div v-else class="rec-list">
          <article v-for="it in dailyRecs" :key="it.book_id" class="rec-card">
            <div class="rec-cover">
              <img :src="coverSrc(it.cover_url)" :alt="it.title" />
            </div>
            <div class="rec-info">
              <div class="rec-title" :title="it.title">{{ it.title || '（无标题）' }}</div>
              <div class="rec-author" :title="it.author">{{ it.author || '作者未知' }}</div>
              <div class="rec-rating">豆瓣评分：{{ formatRating(it.rating) }}</div>
              <div v-if="it.summary" class="rec-summary">{{ truncateText(it.summary, 180) }}</div>
              <button type="button" class="rec-detail" @click="goDetail(it.book_id)">进入详情页</button>
            </div>
          </article>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { booksAPI } from '../api/books'
import { recommendationsAPI } from '../api/recommendations'

const router = useRouter()
const route = useRoute()
const user = ref({})
const showUserMenu = ref(false)
const searchQuery = ref('')
const mode = ref('title')
const genre = ref('')
const mood = ref('')
// 高级搜索已改为“豆瓣直搜”
const books = ref([])
const loading = ref(false)
const fallbackCover =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="320">' +
      '<rect width="100%" height="100%" fill="#f2f3f5"/>' +
      '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#666" font-size="18">No Cover</text>' +
    '</svg>'
  )

const progressVisible = ref(false)
const progress = ref(0)
let progressTimer = null

const doubanStatus = ref({ logged_in: false, login_running: false, last_error: '', cookie_path: '' })
const doubanBusy = ref(false)

const dailyRecs = ref([])
const recLoading = ref(false)
const recError = ref('')
const recLimit = ref(2)
const recCount = ref(0)
const canRefresh = ref(true)

const coverSrc = (url) => {
  if (!url) return fallbackCover
  if (import.meta.env.DEV) {
    return `/api/books/cover?url=${encodeURIComponent(url)}`
  }
  const apiBase = import.meta.env.VITE_API_BASE || ''
  return `${apiBase}/api/books/cover?url=${encodeURIComponent(url)}`
}

const formatRating = (r) => {
  if (r == null) return '暂无'
  if (typeof r === 'number') return r
  if (typeof r === 'string') {
    const s = r.trim()
    if (!s) return '暂无'
    // If someone accidentally cached a JSON string, try to extract value
    try {
      const obj = JSON.parse(s)
      return formatRating(obj)
    } catch {
      return s
    }
  }
  if (typeof r === 'object') {
    if (r.value != null) return formatRating(r.value)
    if (r.score != null) return formatRating(r.score)
    if (r.rating != null) return formatRating(r.rating)
    if (r.rating_info && typeof r.rating_info === 'object') {
      const ri = r.rating_info
      if (ri.value != null) return formatRating(ri.value)
      if (ri.score != null) return formatRating(ri.score)
    }
  }
  return '暂无'
}

const truncateText = (s, maxLen = 140) => {
  const t = (s || '').toString().trim()
  if (!t) return ''
  if (t.length <= maxLen) return t
  return t.slice(0, maxLen).trimEnd() + '…'
}

const loadDaily = async () => {
  recLoading.value = true
  recError.value = ''
  try {
    const res = await recommendationsAPI.today()
    if (res.data?.success) {
      const items = res.data.data?.items || []
      dailyRecs.value = items.length ? [items[items.length - 1]] : []
      recLimit.value = res.data.data?.limit ?? 2
      recCount.value = res.data.data?.count ?? dailyRecs.value.length
      canRefresh.value = !!res.data.data?.can_refresh
    } else {
      recError.value = res.data?.message || '获取每日推荐失败'
    }
  } catch (e) {
    recError.value = e?.response?.data?.message || e?.message || '获取每日推荐失败'
  } finally {
    recLoading.value = false
  }
}

const refreshDaily = async () => {
  recLoading.value = true
  recError.value = ''
  try {
    const res = await recommendationsAPI.refresh()
    if (res.data?.success) {
      const items = res.data.data?.items || []
      dailyRecs.value = items.length ? [items[items.length - 1]] : []
      recLimit.value = res.data.data?.limit ?? 2
      recCount.value = res.data.data?.count ?? dailyRecs.value.length
      canRefresh.value = !!res.data.data?.can_refresh
    } else {
      // 达到每日上限：后端会返回诗意提示 + 现有 items
      recError.value = res.data?.message || '今天的推荐已达到上限'
      const data = res.data?.data
      if (data?.items) {
        dailyRecs.value = data.items.length ? [data.items[data.items.length - 1]] : []
        recLimit.value = data.limit ?? 2
        recCount.value = data.count ?? dailyRecs.value.length
        canRefresh.value = !!data.can_refresh
      } else {
        canRefresh.value = false
      }
    }
  } catch (e) {
    recError.value = e?.response?.data?.message || e?.message || '刷新每日推荐失败'
  } finally {
    recLoading.value = false
  }
}

const cacheKey = (q) => `books_search:${q}`

const startProgress = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  progressVisible.value = true
  progress.value = 10
  // 伪进度：平滑推进到 90%，完成后再跳 100%
  progressTimer = setInterval(() => {
    if (!loading.value) return
    if (progress.value < 90) {
      progress.value += 2
    }
  }, 180)
}

const finishProgress = () => {
  progress.value = 100
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  // 给用户看到“完成”一瞬间
  setTimeout(() => {
    progressVisible.value = false
    progress.value = 0
  }, 350)
}

const userInitial = computed(() => {
  return user.value.username ? user.value.username.charAt(0).toUpperCase() : 'U'
})

onMounted(() => {
  const userData = localStorage.getItem('user')
  if (userData) {
    user.value = JSON.parse(userData)
  }

  const q = (route.query.q || '').toString().trim()
  if (q) {
    searchQuery.value = q
    try {
      const cached = sessionStorage.getItem(cacheKey(q))
      if (cached) {
        const parsed = JSON.parse(cached)
        if (Array.isArray(parsed) && parsed.length > 0) {
          books.value = parsed
          return
        }
        // 空缓存不可靠（可能是临时风控/解析失败），直接忽略并清理
        sessionStorage.removeItem(cacheKey(q))
      }
    } catch {
      // ignore cache errors
    }
    handleSearch(false)
  }

  refreshDoubanStatus()
  loadDaily()
})

const refreshDoubanStatus = async () => {
  try {
    doubanBusy.value = true
    const res = await booksAPI.doubanStatus()
    if (res.data?.success) {
      doubanStatus.value = res.data.status || doubanStatus.value
    }
  } finally {
    doubanBusy.value = false
  }
}

const triggerDoubanLogin = async () => {
  try {
    doubanBusy.value = true
    const res = await booksAPI.doubanLogin(false, 240)
    if (res.data?.success) {
      alert(res.data?.message || '已打开浏览器，请完成豆瓣登录')
      doubanStatus.value = res.data.status || doubanStatus.value
    } else {
      alert(res.data?.message || '豆瓣登录失败')
    }
  } finally {
    doubanBusy.value = false
  }
}

const triggerDoubanLogout = async () => {
  try {
    doubanBusy.value = true
    const res = await booksAPI.doubanLogout()
    if (res.data?.success) {
      alert(res.data?.message || '已清除豆瓣登录态')
      doubanStatus.value = res.data.status || doubanStatus.value
    } else {
      alert(res.data?.message || '退出豆瓣失败')
    }
  } finally {
    doubanBusy.value = false
  }
}


const handleSearch = async (updateRoute = true) => {
  const q = searchQuery.value.trim()
  if (mode.value !== 'advanced' && !q) return

  try {
    if (mode.value !== 'advanced') {
      if (updateRoute) {
        router.replace({ path: '/', query: { q } })
      }

      const cached = sessionStorage.getItem(cacheKey(q))
      if (cached) {
        const parsed = JSON.parse(cached)
        if (Array.isArray(parsed) && parsed.length > 0) {
          books.value = parsed
          // 命中缓存也给一个非常快的完成反馈
          loading.value = true
          startProgress()
          loading.value = false
          finishProgress()
          return
        }
        // 空缓存不可靠（可能是临时风控/解析失败），丢弃并继续走网络请求
        sessionStorage.removeItem(cacheKey(q))
      }
    }
  } catch {
    // ignore cache errors
  }

  loading.value = true
  startProgress()
  books.value = []
  try {
    if (mode.value === 'advanced') {
      const g = genre.value.trim()
      const m = mood.value.trim()
      if (!g || !m) {
        alert('请先选择书籍类型，并输入描述')
        return
      }
      const res = await booksAPI.advancedSearch({ genre: g, text: m, limit: 50 })
      if (res.data?.success) {
        books.value = res.data.data || []
      } else {
        alert(res.data?.message || '高级搜索失败')
      }
    } else {
      // title/author 都走豆瓣关键词搜索
      const res = await booksAPI.search(q, 50)
      if (res.data?.success) {
        books.value = res.data.data || []
        try {
          // 避免把“临时风控/解析失败导致的空结果”缓存住
          if (Array.isArray(books.value) && books.value.length > 0) {
            sessionStorage.setItem(cacheKey(q), JSON.stringify(books.value))
          } else {
            sessionStorage.removeItem(cacheKey(q))
          }
        } catch {
          // ignore cache errors
        }
      } else {
        alert(res.data?.message || '搜索失败')
      }
    }
  } finally {
    loading.value = false
    finishProgress()
  }
}

const goDetail = (bookId) => {
  const q = searchQuery.value.trim()
  router.push({ path: `/book/${bookId}`, query: q ? { q } : {} })
}

const goToBookshelf = () => {
  showUserMenu.value = false
  router.push({ name: 'Bookshelf' })
}

const goToProfile = () => {
  showUserMenu.value = false
  router.push({ name: 'Profile' })
}

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/auth')
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background: transparent;
}

.header {
  background: var(--glass-bg);
  border: 1px solid rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
  padding: 0 20px;
  position: relative;
  z-index: 10;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 70px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ext-link {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.75);
  color: var(--ink);
  font-weight: 800;
  text-decoration: none;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.06);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.ext-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 26px rgba(0, 0, 0, 0.10);
}


.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 42px;
  height: 42px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.05;
}

.brand-title {
  font-size: 18px;
  font-weight: 900;
  color: var(--ink);
  letter-spacing: 1px;
  font-family: ui-serif, Georgia, 'Times New Roman', 'KaiTi', 'STKaiti', serif;
}

.brand-sub {
  margin-top: 6px;
  font-size: 12px;
  font-weight: 800;
  color: var(--ink-soft);
  letter-spacing: 0.6px;
}

.user-menu {
  position: relative;
}

.user-avatar {
  width: 45px;
  height: 45px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(255, 214, 231, 1), rgba(217, 230, 255, 1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4b4b5a;
  font-weight: bold;
  font-size: 18px;
  cursor: pointer;
  transition: transform 0.2s;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.10);
}

.user-avatar:hover {
  transform: scale(1.05);
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 55px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  padding: 12px;
  min-width: 200px;
  z-index: 1000;
}

.user-info {
  padding: 12px;
}

.username {
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.email {
  font-size: 13px;
  color: #666;
}

.menu-divider {
  height: 1px;
  background: #e0e0e0;
  margin: 8px 0;
}

.menu-item {
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  border-radius: 8px;
  font-size: 14px;
  color: #333;
  transition: background 0.2s;
}

.menu-item:hover {
  background: #f5f5f5;
}

.menu-item.logout {
  color: #e53e3e;
}

.douban-auth {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.douban-status {
  font-size: 13px;
  color: var(--ink-soft);
}

.douban-status .label {
  font-weight: 700;
  color: var(--ink);
}

.douban-status .ok {
  font-weight: 800;
}

.douban-status .pending {
  font-weight: 800;
}

.douban-status .bad {
  font-weight: 800;
}

.douban-status .err {
  margin-left: 6px;
  opacity: 0.8;
}

.douban-actions {
  display: flex;
  gap: 8px;
}

.mini {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.55);
  background: var(--glass-bg);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}

.mini:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.mini.primary {
  font-weight: 900;
}

.menu-item.logout:hover {
  background: #fee;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 60px 20px;
}

.search-section {
  text-align: center;
  margin-bottom: 60px;
  position: relative;
}

.search-modes {
  display: flex;
  gap: 8px;
  margin: 10px 0 12px;
}

.mode {
  border: 0;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 8px 12px;
  border-radius: 999px;
  font-weight: 900;
  cursor: pointer;
}

.mode.active {
  background: rgba(217, 230, 255, 0.65);
}

.select {
  border: 1px solid rgba(0, 0, 0, 0.10);
  border-radius: 12px;
  padding: 10px 38px 10px 12px;
  background: rgba(255, 255, 255, 0.62);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  color: var(--ink);
}

.select option {
  background: rgba(255, 255, 255, 0.92);
}

.select-wrap {
  position: relative;
  display: inline-flex;
  flex: 0 0 auto;
}

.select-wrap::after {
  content: '▾';
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--ink-soft);
  pointer-events: none;
  font-size: 14px;
  font-weight: 900;
}

.link {
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 900;
  cursor: pointer;
  text-decoration: underline;
}

.link:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.welcome-text {
  font-size: 38px;
  font-weight: 900;
  color: var(--ink);
  margin-bottom: 32px;
  font-family: ui-serif, Georgia, 'Times New Roman', 'KaiTi', 'STKaiti', serif;
  letter-spacing: 1.2px;
}

.search-box {
  display: flex;
  max-width: 700px;
  margin: 0 auto;
  gap: 12px;
}

.search-box input {
  flex: 1;
  padding: 16px 24px;
  border: 2px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  font-size: 16px;
  transition: border-color 0.3s;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
}

.search-box input:focus {
  outline: none;
  border-color: rgba(255, 214, 231, 1);
}

.search-btn {
  padding: 16px 32px;
  background: linear-gradient(135deg, rgba(255, 214, 231, 1), rgba(217, 230, 255, 1));
  color: #2f2f39;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.10);
}

.search-btn:hover {
  filter: brightness(0.98);
}

.progress-wrap {
  width: min(720px, 92vw);
  margin: 12px auto 0;
}

.progress-bar {
  height: 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 214, 231, 1), rgba(217, 230, 255, 1));
  transition: width 0.18s ease;
}

.progress-text {
  margin-top: 8px;
  font-size: 13px;
  opacity: 0.85;
}

.results {
  width: min(1100px, 92vw);
  margin: 24px auto 0;
}

.results-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.results-header h3 {
  margin: 0;
}

.meta {
  opacity: 0.8;
  font-size: 13px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.book-card {
  cursor: pointer;
  background: rgba(255, 255, 255, 0.70);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  overflow: hidden;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  backdrop-filter: blur(10px);
}

.book-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.12);
}

.cover {
  aspect-ratio: 3 / 4;
  background: #f3f3f3;
}

.cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.info {
  padding: 8px 10px 10px;
}

.title {
  font-weight: 700;
  font-size: 14px;
  line-height: 1.2;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 34px;
}

.author {
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.85;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rating {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.score {
  font-size: 16px;
  font-weight: 800;
  color: #4b4b5a;
}

.hint {
  font-size: 12px;
  opacity: 0.7;
}

.recommendations {
  margin-top: 26px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(10px);
  padding: 26px;
  border-radius: 16px;
  box-shadow: var(--glass-shadow);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.recommendations h3 {
  font-size: 18px;
  color: #111;
  margin-bottom: 16px;
  font-weight: 900;
  letter-spacing: 1px;
  font-family: ui-serif, Georgia, 'Times New Roman', 'KaiTi', 'STKaiti', serif;
}

.rec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.rec-meta {
  font-size: 13px;
  color: var(--ink-soft);
  font-weight: 800;
}

.rec-refresh {
  appearance: none;
  border: 0;
  background: rgba(0, 0, 0, 0.06);
  color: var(--ink);
  font-weight: 800;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.rec-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.rec-state {
  color: var(--ink-soft);
  font-size: 14px;
  text-align: center;
  padding: 18px 0;
  font-weight: 800;
}

.rec-state.error {
  color: var(--ink);
}

.rec-list {
  display: grid;
  gap: 12px;
}

.rec-card {
  display: grid;
  grid-template-columns: 84px 1fr;
  gap: 12px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.70);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.rec-cover img {
  width: 84px;
  height: 112px;
  object-fit: cover;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fff;
}

.rec-title {
  font-weight: 900;
  color: var(--ink);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-author {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-soft);
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-rating {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-soft);
  font-weight: 800;
}

.rec-summary {
  margin-top: 8px;
  font-size: 13px;
  color: var(--ink);
  line-height: 1.65;
  white-space: pre-wrap;
}

.rec-detail {
  margin-top: 10px;
  appearance: none;
  border: 0;
  background: rgba(0, 0, 0, 0.06);
  color: var(--ink);
  font-weight: 800;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.rec-detail:hover,
.rec-refresh:hover {
  background: rgba(0, 0, 0, 0.08);
}
</style>
