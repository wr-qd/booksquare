<template>
  <div class="page">
    <header class="topbar">
      <div class="left">
        <button class="back" type="button" @click="goHome">返回</button>
        <h2>我的书架</h2>
      </div>
      <button class="logout" type="button" @click="logout">退出登录</button>
    </header>

    <main class="content">
      <div v-if="loading" class="hint">加载中…</div>
      <div v-else-if="!items.length" class="empty">还没有书。可以先添加一本自定义书籍。</div>

      <section v-if="!loading" class="grid">
        <input
          ref="uploadInput"
          class="hidden-input"
          type="file"
          accept=".txt,.epub"
          @change="onPicked"
        />
        <article class="card add" role="button" tabindex="0" @click="goCreate" @keyup.enter="goCreate">
          <div class="add-inner">
            <div class="plus">+</div>
            <div class="add-text">自定义书籍</div>
          </div>
        </article>

        <article v-for="it in items" :key="it.id" class="card">
          <div class="cover" role="button" tabindex="0" @click="openDetail(it.book_id)">
            <img :src="coverSrc(it.book_cover)" :alt="it.book_title" />
          </div>
          <div class="info" role="button" tabindex="0" @click="openDetail(it.book_id)">
            <div class="title" :title="it.book_title">{{ it.book_title }}</div>
            <div class="author" :title="it.book_author">{{ it.book_author || '作者未知' }}</div>
            <div class="rating">
              <span class="score">{{ it.book_rating ?? '暂无' }}</span>
              <span class="hint">豆瓣评分</span>
            </div>
          </div>
          <div class="actions">
            <button
              class="action-btn primary"
              type="button"
              :disabled="!resumeMap[it.book_id]"
              @click="continueReading(it.book_id)"
            >
              继续阅读
            </button>
            <button
              class="action-btn"
              type="button"
              :disabled="uploadingBookId === it.book_id"
              @click="triggerUpload(it.book_id)"
            >
              {{ uploadingBookId === it.book_id ? '上传中…' : '上传并阅读' }}
            </button>
          </div>
          <div class="actions secondary">
            <button
              class="action-btn ghost"
              type="button"
              @click="openThoughts(it)"
            >
              我的感想
            </button>
            <button class="action-btn danger" type="button" @click="remove(it.book_id)">
              移除
            </button>
          </div>
        </article>
      </section>

      <div v-if="thoughtsVisible" class="thoughts-mask" @click="closeThoughts">
        <div class="thoughts-panel" @click.stop>
          <div class="thoughts-head">
            <div>
              <div class="thoughts-title">我的感想</div>
              <div class="thoughts-sub">{{ thoughtsBook?.book_title || '' }}</div>
            </div>
            <button class="thoughts-close" type="button" @click="closeThoughts">×</button>
          </div>

          <div class="thoughts-body">
            <div v-if="thoughtsLoading" class="hint">加载中…</div>
            <div v-else-if="thoughtsError" class="hint error">{{ thoughtsError }}</div>
            <div v-else-if="!thoughtsNotes.length" class="hint">还没有随笔或收藏句子。</div>
            <div v-else class="timeline">
              <div v-for="note in thoughtsNotes" :key="note.id" class="tl-item">
                <div class="tl-dot"></div>
                <div class="tl-line"></div>
                <div class="tl-card">
                  <div class="tl-meta">
                    <span>{{ note.kind === 'quote' ? '收藏句子' : '随笔' }} · {{ formatTime(note.created_at) }}</span>
                    <button
                      class="tl-remove"
                      type="button"
                      :disabled="removingNoteId === note.id"
                      @click="deleteNote(note)"
                    >
                      {{ removingNoteId === note.id ? '删除中…' : '删除' }}
                    </button>
                  </div>
                  <div v-if="note.quote_text" class="tl-quote">“{{ note.quote_text }}”</div>
                  <div v-if="note.content" class="tl-text">{{ note.content }}</div>
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
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { meAPI } from '../api/me'
import { readerAPI } from '../api/reader'

const router = useRouter()

const items = ref([])
const loading = ref(true)
const resumeMap = ref({})
const uploadingBookId = ref('')
const uploadInput = ref(null)
const pendingBookId = ref('')
const thoughtsVisible = ref(false)
const thoughtsLoading = ref(false)
const thoughtsError = ref('')
const thoughtsNotes = ref([])
const thoughtsBook = ref(null)
const removingNoteId = ref(0)

const fallbackCover =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="320">' +
      '<rect width="100%" height="100%" fill="#f2f3f5"/>' +
      '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#666" font-size="18">No Cover</text>' +
    '</svg>'
  )

const coverSrc = (url) => {
  if (!url) return fallbackCover
  // 自定义书籍封面可能是本地 /api/... 路径
  if (url.startsWith('/api/')) {
    if (import.meta.env.DEV) return url
    const apiBase = import.meta.env.VITE_API_BASE || ''
    return `${apiBase}${url}`
  }
  if (import.meta.env.DEV) {
    return `/api/books/cover?url=${encodeURIComponent(url)}`
  }
  const apiBase = import.meta.env.VITE_API_BASE || ''
  return `${apiBase}/api/books/cover?url=${encodeURIComponent(url)}`
}

const load = async () => {
  loading.value = true
  try {
    const res = await meAPI.listBookshelf()
    items.value = res.data?.data?.items || []
    await Promise.all(items.value.map((it) => loadResume(it.book_id)))
  } finally {
    loading.value = false
  }
}

const loadResume = async (bookId) => {
  try {
    const res = await readerAPI.assets(bookId)
    if (res.data?.success) {
      const list = res.data.data?.items || []
      resumeMap.value = { ...resumeMap.value, [bookId]: list.length ? String(list[0].id) : '' }
    } else {
      resumeMap.value = { ...resumeMap.value, [bookId]: '' }
    }
  } catch {
    resumeMap.value = { ...resumeMap.value, [bookId]: '' }
  }
}

const continueReading = (bookId) => {
  const assetId = resumeMap.value[bookId]
  if (!assetId) return
  router.push({ name: 'ReaderView', params: { assetId: String(assetId) } })
}

const triggerUpload = (bookId) => {
  pendingBookId.value = String(bookId)
  uploadInput.value?.click()
}

const openThoughts = async (book) => {
  thoughtsBook.value = book
  thoughtsVisible.value = true
  thoughtsError.value = ''
  thoughtsNotes.value = []
  thoughtsLoading.value = true
  try {
    const res = await meAPI.listNotes(book.book_id)
    if (res.data?.success) {
      thoughtsNotes.value = res.data.data?.items || []
    } else {
      thoughtsError.value = res.data?.message || '加载失败'
    }
  } catch (e) {
    thoughtsError.value = e?.response?.data?.message || e?.message || '加载失败'
  } finally {
    thoughtsLoading.value = false
  }
}

const closeThoughts = () => {
  thoughtsVisible.value = false
  thoughtsBook.value = null
  thoughtsNotes.value = []
  thoughtsError.value = ''
}

const onPicked = async (e) => {
  const file = e?.target?.files?.[0]
  // reset input value so the same file can be picked again next time
  if (e?.target) e.target.value = ''
  if (!file || !pendingBookId.value) return
  uploadingBookId.value = pendingBookId.value
  try {
    const res = await readerAPI.upload({ bookId: pendingBookId.value, file, title: file.name })
    if (res.data?.success) {
      const assetId = res.data.data?.asset?.id
      await loadResume(pendingBookId.value)
      if (assetId) {
        router.push({ name: 'ReaderView', params: { assetId: String(assetId) } })
      }
    }
  } catch (err) {
    console.error('upload failed', err)
  } finally {
    uploadingBookId.value = ''
    pendingBookId.value = ''
  }
}

const remove = async (bookId) => {
  await meAPI.unlikeBook(bookId)
  items.value = items.value.filter((x) => x.book_id !== bookId)
}

const deleteNote = async (note) => {
  if (!note?.id) return
  removingNoteId.value = note.id
  try {
    await meAPI.deleteNote(note.id)
    thoughtsNotes.value = thoughtsNotes.value.filter((n) => n.id !== note.id)
  } catch (e) {
    thoughtsError.value = e?.response?.data?.message || e?.message || '删除失败'
  } finally {
    removingNoteId.value = 0
  }
}

const openDetail = (bookId) => {
  router.push(`/book/${bookId}`)
}

const goCreate = () => {
  router.push({ name: 'CreateCustomBook' })
}

const goHome = () => router.push('/')

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/auth')
}

const formatTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${day} ${hh}:${mm}`
  } catch {
    return iso
  }
}

onMounted(() => {
  load()
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
  width: min(1100px, 92vw);
  margin: 18px auto 40px;
}

.hint,
.empty {
  color: #555;
  font-size: 14px;
  padding: 18px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}

.card {
  background: rgba(255, 255, 255, 0.70);
  backdrop-filter: blur(10px);
  box-shadow: var(--glass-shadow);
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card.add {
  cursor: pointer;
  align-items: center;
  justify-content: center;
  min-height: 330px;
  background: rgba(255, 255, 255, 0.55);
  border-style: dashed;
}

.add-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 18px;
}

.plus {
  width: 68px;
  height: 68px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 900;
  color: #111;
  line-height: 1;
}

.add-text {
  font-weight: 900;
  color: #111;
}

.cover {
  height: 220px;
  background: #f2f3f5;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.info {
  padding: 12px;
  cursor: pointer;
}

.title {
  font-weight: 900;
  color: #111;
  font-size: 14px;
  line-height: 1.25;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.author {
  margin-top: 6px;
  color: #666;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rating {
  margin-top: 10px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.score {
  font-weight: 900;
  color: #111;
}

.rating .hint {
  color: #888;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 10px;
  padding: 0 12px 12px;
}

.hidden-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.action-btn {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.85);
  padding: 9px 12px;
  border-radius: 12px;
  font-weight: 900;
  cursor: pointer;
  color: #111;
  flex: 1;
}

.action-btn.primary {
  background: #0f172a;
  color: #fff;
  border-color: #0f172a;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.18);
}

.action-btn.ghost {
  background: rgba(15, 23, 42, 0.06);
  border-color: rgba(15, 23, 42, 0.12);
  color: #0f172a;
}

.action-btn.danger {
  background: rgba(220, 38, 38, 0.12);
  border-color: rgba(220, 38, 38, 0.25);
  color: #b91c1c;
  box-shadow: none;
}

.actions.secondary {
  justify-content: flex-start;
  margin-top: 8px;
  gap: 10px;
  padding: 0 12px 12px;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.thoughts-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(2px);
  display: grid;
  place-items: center;
  z-index: 20;
}

.thoughts-panel {
  width: min(760px, 92vw);
  max-height: 80vh;
  background: #fdfdfd;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.16);
  padding: 18px;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 12px;
}

.thoughts-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.thoughts-title {
  font-weight: 900;
  font-size: 18px;
  color: #0f172a;
}

.thoughts-sub {
  color: #555;
  font-size: 13px;
  margin-top: 4px;
}

.thoughts-close {
  background: transparent;
  border: none;
  font-size: 20px;
  cursor: pointer;
}

.thoughts-body {
  overflow: auto;
  padding: 6px 2px 2px;
}

.timeline {
  position: relative;
  padding-left: 16px;
}

.tl-item {
  position: relative;
  padding-left: 22px;
  margin-bottom: 16px;
}

.tl-dot {
  position: absolute;
  left: 0;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0f172a, #3b82f6);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.12);
}

.tl-line {
  position: absolute;
  left: 4px;
  top: 16px;
  width: 2px;
  height: calc(100% - 10px);
  background: rgba(0, 0, 0, 0.08);
}

.tl-card {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.06);
}

.tl-meta {
  font-size: 12px;
  color: #555;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tl-remove {
  border: 0;
  background: rgba(220, 38, 38, 0.12);
  color: #b91c1c;
  border-radius: 8px;
  padding: 4px 8px;
  cursor: pointer;
  font-weight: 700;
  font-size: 12px;
}

.tl-remove:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.tl-quote {
  font-size: 14px;
  color: #0f172a;
  margin-bottom: 6px;
  font-weight: 600;
}

.tl-text {
  font-size: 13px;
  color: #444;
  line-height: 1.6;
}

</style>
