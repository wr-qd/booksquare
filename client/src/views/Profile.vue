<template>
  <div class="page">
    <header class="topbar">
      <div class="left">
        <button class="back" type="button" @click="goHome">返回</button>
        <h2>个人信息</h2>
      </div>
      <button class="logout" type="button" @click="logout">退出登录</button>
    </header>

    <main class="content">
      <div class="card">
        <div class="row">
          <div class="label">用户名</div>
          <div class="value">{{ user.username || '-' }}</div>
        </div>
        <div class="row">
          <div class="label">邮箱</div>
          <div class="value">{{ user.email || '-' }}</div>
        </div>
        <div class="row">
          <div class="label">注册时间</div>
          <div class="value">{{ user.created_at || '-' }}</div>
        </div>
      </div>

      <div class="card timeline">
        <h3 class="card-title">读书日记</h3>
        <div class="timeline-layout">
          <aside class="filters" aria-label="按书籍筛选">
            <div class="filters-title">书籍</div>
            <button
              class="filter-item"
              type="button"
              :class="{ active: selectedBookId === 'all' }"
              @click="selectBook('all')"
            >
              全部日记
            </button>

            <div v-if="loadingShelf" class="filters-hint">加载书架…</div>
            <div v-else-if="!shelfItems.length" class="filters-hint">书架为空</div>
            <button
              v-else
              v-for="it in shelfItems"
              :key="it.book_id"
              class="filter-item"
              type="button"
              :class="{ active: selectedBookId === it.book_id }"
              @click="selectBook(it.book_id)"
              :title="it.book_title"
            >
              {{ it.book_title }}
            </button>
          </aside>

          <div class="timeline-main">
            <div v-if="loadingLogs" class="hint">加载中…</div>
            <div v-else-if="!sortedLogs.length" class="hint">还没有读书日记，去书籍详情页写一条吧。</div>
            <div v-else class="fishbone" aria-label="鱼骨读书日记">
              <div
                v-for="(it, idx) in sortedLogs"
                :key="it.id"
                :class="['bone', idx % 2 === 0 ? 'bone-left' : 'bone-right']"
              >
                <div class="bone-card">
                  <div class="bone-actions">
                    <button class="bone-btn" type="button" @click="goBookDetail(it.book_id)">详情</button>
                    <button
                      class="bone-btn danger"
                      type="button"
                      :disabled="deletingIds.has(it.id)"
                      @click="removeLog(it.id)"
                    >
                      {{ deletingIds.has(it.id) ? '移除中…' : '移除' }}
                    </button>
                  </div>
                  <div class="bone-meta">
                    <span class="bone-date">{{ formatMoment(it.created_at) }}</span>
                    <span class="bone-book">《{{ it.book_title }}》</span>
                  </div>
                  <div class="bone-content">{{ it.content }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '../api/auth'
import { meAPI } from '../api/me'

const router = useRouter()
const user = ref({})
const logs = ref([])
const loadingLogs = ref(false)
const deletingIds = ref(new Set())
const shelfItems = ref([])
const loadingShelf = ref(false)
const selectedBookId = ref('all')

// 需求：上新下旧（越往下越旧）
const sortedLogs = computed(() => {
  const arr = Array.isArray(logs.value) ? [...logs.value] : []
  arr.sort((a, b) => {
    const ta = a?.created_at ? Date.parse(a.created_at) : 0
    const tb = b?.created_at ? Date.parse(b.created_at) : 0
    return (Number.isFinite(tb) ? tb : 0) - (Number.isFinite(ta) ? ta : 0)
  })
  return arr
})

const formatDay = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  } catch {
    return iso
  }
}

const formatMoment = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const ymd = formatDay(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${ymd} ${hh}:${mm}`
  } catch {
    return iso
  }
}

const load = async () => {
  // 优先用本地缓存，失败再请求后端
  const cached = localStorage.getItem('user')
  if (cached) {
    try {
      user.value = JSON.parse(cached) || {}
    } catch {
      // ignore
    }
  }

  try {
    const res = await authAPI.getProfile()
    if (res.data?.user) {
      user.value = res.data.user
      localStorage.setItem('user', JSON.stringify(user.value))
    }
  } catch {
    // ignore
  }
}

const loadTimeline = async () => {
  loadingLogs.value = true
  try {
    if (selectedBookId.value === 'all') {
      const res = await meAPI.listReadingLogs(200)
      logs.value = res.data?.data?.items || []
    } else {
      const res = await meAPI.listBookReadingLogs(selectedBookId.value)
      logs.value = res.data?.data?.items || []
    }
  } finally {
    loadingLogs.value = false
  }
}

const loadShelf = async () => {
  loadingShelf.value = true
  try {
    const res = await meAPI.listBookshelf()
    shelfItems.value = res.data?.data?.items || []
  } finally {
    loadingShelf.value = false
  }
}

const selectBook = async (bookId) => {
  selectedBookId.value = bookId || 'all'
  await loadTimeline()
}

const goHome = () => router.push('/')

const goBookDetail = (bookId) => {
  if (!bookId) return
  router.push({ name: 'BookDetail', params: { id: String(bookId) } })
}

const removeLog = async (logId) => {
  if (!logId) return
  if (!confirm('确定要移除这条读书日记吗？')) return

  const set = deletingIds.value
  if (set.has(logId)) return

  set.add(logId)
  try {
    const res = await meAPI.deleteReadingLog(logId)
    const deleted = !!res.data?.data?.deleted
    if (deleted) {
      logs.value = (Array.isArray(logs.value) ? logs.value : []).filter((x) => x?.id !== logId)
    }
  } catch (e) {
    const msg = e?.response?.data?.error || e?.response?.data?.message || e?.message || '移除失败'
    alert(String(msg))
  } finally {
    set.delete(logId)
    deletingIds.value = new Set(set)
  }
}

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/auth')
}

onMounted(() => {
  load()
  loadShelf()
  loadTimeline()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: transparent;
}

.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  background: var(--glass-bg);
  border-bottom: 1px solid rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
}

.topbar h2 {
  font-size: 18px;
  font-weight: 900;
  color: var(--ink);
  letter-spacing: 1px;
  font-family: ui-serif, Georgia, 'Times New Roman', 'KaiTi', 'STKaiti', serif;
}

.left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.back {
  border: 0;
  background: rgba(255, 255, 255, 0.55);
  padding: 8px 12px;
  border-radius: 10px;
  font-weight: 800;
  cursor: pointer;
}

.logout {
  border: 0;
  background: rgba(255, 255, 255, 0.55);
  padding: 8px 12px;
  border-radius: 10px;
  font-weight: 800;
  cursor: pointer;
}

.content {
  width: min(900px, 92vw);
  margin: 18px auto 40px;
}

.card {
  background: rgba(255, 255, 255, 0.70);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 16px;
}

.timeline {
  margin-top: 14px;
}

.timeline-layout {
  display: grid;
  grid-template-columns: 210px 1fr;
  gap: 12px;
  align-items: start;
}

.filters {
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  padding: 12px;
  backdrop-filter: blur(10px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 76px;
  max-height: calc(100vh - 110px);
  overflow: auto;
}

.filters-title {
  font-weight: 900;
  color: #111;
  margin-bottom: 10px;
  letter-spacing: 1px;
  font-family: ui-serif, Georgia, 'Times New Roman', 'KaiTi', 'STKaiti', serif;
}

.filter-item {
  width: 100%;
  text-align: left;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.60);
  padding: 10px 10px;
  border-radius: 12px;
  font-weight: 900;
  cursor: pointer;
  margin-bottom: 8px;
  color: #111;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-item.active {
  background: rgba(217, 230, 255, 0.65);
}

.filters-hint {
  color: #666;
  font-size: 12px;
  font-weight: 800;
  padding: 8px 2px;
}

.timeline-main {
  min-width: 0;
}

.card-title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 900;
  color: #111;
}

.hint {
  color: #666;
  font-size: 13px;
  font-weight: 800;
  padding: 8px 0;
}

.fishbone {
  position: relative;
  margin-top: 8px;
  padding: 6px 0 10px;
}

.fishbone::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 4px;
  transform: translateX(-50%);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 214, 231, 0.9), rgba(217, 230, 255, 0.9));
}

.bone {
  position: relative;
  display: flex;
  padding: 12px 0;
  min-height: 84px;
}

.bone::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 12px;
  height: 12px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  background: #fff;
  border: 3px solid rgba(255, 214, 231, 0.95);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.06);
}

.bone-left {
  justify-content: flex-end;
}

.bone-right {
  justify-content: flex-start;
}

.bone-card {
  position: relative;
  width: min(420px, 44vw);
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 16px;
  padding: 12px 14px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(6px);
}

.bone-actions {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 8px;
}

.bone-btn {
  border: 0;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 6px 10px;
  border-radius: 999px;
  font-weight: 900;
  font-size: 12px;
  cursor: pointer;
}

.bone-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.bone-btn.danger {
  background: rgba(255, 230, 236, 0.75);
}

.bone-left .bone-card {
  margin-right: calc(50% - 10px);
}

.bone-right .bone-card {
  margin-left: calc(50% - 10px);
}

.bone-left .bone-card::after,
.bone-right .bone-card::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 68px;
  height: 2px;
  background: rgba(0, 0, 0, 0.10);
  transform-origin: center;
}

.bone-left .bone-card::after {
  right: -60px;
  transform: translateY(-50%) rotate(18deg);
}

.bone-right .bone-card::after {
  left: -60px;
  transform: translateY(-50%) rotate(-18deg);
}

.bone-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
}

.bone-date {
  font-size: 12px;
  font-weight: 900;
  color: #3b3b49;
  background: rgba(217, 230, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 4px 8px;
  border-radius: 999px;
}

.bone-book {
  font-size: 13px;
  font-weight: 900;
  color: #111;
}

.bone-content {
  margin-top: 8px;
  color: #2f2f39;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

/* 屏幕稍窄也保持鱼骨（只有非常窄才回退为单列） */
@media (max-width: 520px) {
  .timeline-layout {
    grid-template-columns: 1fr;
  }

  .filters {
    position: relative;
    top: auto;
    max-height: none;
  }

  .fishbone::before {
    left: 16px;
    transform: none;
  }

  .bone {
    padding-left: 16px;
  }

  .bone::before {
    left: 16px;
    transform: translate(-50%, -50%);
  }

  .bone-card {
    width: 100%;
    margin: 0 0 0 28px !important;
  }

  .bone-left .bone-card::after,
  .bone-right .bone-card::after {
    left: -28px;
    right: auto;
    width: 28px;
    transform: translateY(-50%);
  }
}

.row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.row:last-child {
  border-bottom: 0;
}

.label {
  color: #666;
  font-size: 13px;
  font-weight: 800;
}

.value {
  color: #111;
  font-size: 14px;
  font-weight: 900;
  text-align: right;
  max-width: 70%;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
