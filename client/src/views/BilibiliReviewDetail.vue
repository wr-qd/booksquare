<template>
  <div class="detail">
    <div class="card">
      <div class="head">
        <img
          class="home-icon"
          src="../assets/brand-mark.svg"
          alt="回到首页"
          role="button"
          tabindex="0"
          @click="goHome"
          @keyup.enter="goHome"
        />
        <button class="back" type="button" @click="goBack">返回</button>
        <div class="title">{{ item.title || 'B站书评' }}</div>
        <a v-if="item.url" class="origin" :href="item.url" target="_blank" rel="noreferrer">原文</a>
      </div>

      <div class="meta">
        <span v-if="item.author" class="author">评价人：{{ item.author }}</span>
        <span v-else class="author">评价人：未知</span>
        <span class="dot">·</span>
        <span class="book">关联书籍：{{ bookId }}</span>
      </div>

      <div v-if="loading" class="state">加载中…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <div v-else class="body">
        <div v-if="proxiedHtml" class="html" v-html="proxiedHtml"></div>
        <div v-else class="state">暂无正文</div>

        <div v-if="images.length" class="images">
          <div class="images-title">图片</div>
          <div class="grid">
            <a v-for="(u, idx) in images" :key="u + idx" class="img" :href="u" target="_blank" rel="noreferrer">
              <img :src="proxyImageUrl(u)" alt="img" loading="lazy" referrerpolicy="no-referrer" />
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { booksAPI } from '../api/books'

const route = useRoute()
const router = useRouter()

const bookId = computed(() => route.params.id)
const cvId = computed(() => route.params.cvId)

const loading = ref(true)
const error = ref('')
const item = ref({})

const images = computed(() => item.value.images || [])

const proxyImageUrl = (u) => {
  if (!u) return ''
  const url = String(u).startsWith('//') ? `https:${u}` : String(u)
  return `/api/books/bilibili/image?url=${encodeURIComponent(url)}`
}

const proxiedHtml = computed(() => {
  const raw = item.value.content_html || ''
  if (!raw) return ''

  // 1) Normalize protocol-less urls.
  let html = String(raw).replace(/\bsrc=(['"])\/\//gi, 'src=$1https://')
  html = html.replace(/\bdata-src=(['"])\/\//gi, 'data-src=$1https://')

  // 2) Prefer https.
  html = html.replace(/\bsrc=(['"])http:\/\//gi, 'src=$1https://')
  html = html.replace(/\bdata-src=(['"])http:\/\//gi, 'data-src=$1https://')

  // 3) Proxy all images to avoid 404/hotlink issues.
  html = html.replace(/\bsrc=(['"])([^'"\s>]+)\1/gi, (m, q, url) => {
    if (!/^https?:\/\//i.test(url)) return m
    return `src=${q}${proxyImageUrl(url)}${q}`
  })

  // 4) Ensure no-referrer on images.
  html = html.replace(/<img\b(?![^>]*\breferrerpolicy=)/gi, '<img referrerpolicy="no-referrer"')

  return html
})

const goBack = () => {
  const id = String(bookId.value || '')
  const back = router?.options?.history?.state?.back
  const backStr = back == null ? '' : String(back)

  // If we have a proper back entry to the book detail page, use it to preserve
  // scroll position and already-loaded data.
  if (backStr.includes(`/book/${id}`)) {
    router.back()
    return
  }

  // Fallback (e.g. user refreshed the detail page so there's no SPA history).
  router.push({
    name: 'BookDetail',
    params: { id },
    query: { tab: 'bilibili', restore: '1' },
  })
}

const goHome = () => {
  router.push({ name: 'Home' })
}

const init = async () => {
  loading.value = true
  error.value = ''
  try {
    const id = String(cvId.value || '').replace(/^cv/i, '')
    const res = await booksAPI.bilibiliArticle(id)
    if (res.data?.success) {
      item.value = res.data.data || {}
    } else {
      error.value = res.data?.message || '加载失败'
    }
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  init()
})
</script>

<style scoped>
.detail {
  padding: 18px;
}

.card {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.60);
  border-radius: 16px;
  box-shadow: var(--glass-shadow);
  padding: 16px;
}

.head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.home-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.70);
  border: 1px solid rgba(0, 0, 0, 0.08);
  cursor: pointer;
}

.back {
  border: 1px solid rgba(0, 0, 0, 0.10);
  background: rgba(255, 255, 255, 0.70);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--ink);
}

.title {
  flex: 1;
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.origin {
  font-size: 14px;
  color: var(--ink-soft);
  text-decoration: none;
}

.origin:hover {
  text-decoration: underline;
}

.meta {
  margin-top: 10px;
  color: var(--ink-soft);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dot {
  opacity: 0.6;
}

.state {
  margin-top: 14px;
  color: var(--ink-soft);
}

.state.error {
  color: #c33;
}

.body {
  margin-top: 14px;
}

.html :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 10px auto;
  border-radius: 10px;
}

.images {
  margin-top: 14px;
}

.images-title {
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 10px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}

.img {
  display: block;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.75);
}

.img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
