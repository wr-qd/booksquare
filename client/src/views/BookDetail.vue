<template>
  <div class="detail">
    <img
      class="home-icon"
      src="../assets/brand-mark.svg"
      alt="回到首页"
      role="button"
      tabindex="0"
      @click="goHome"
      @keyup.enter="goHome"
    />

    <div class="hero" :style="heroStyle">
      <div class="glass">
        <div v-if="loadingDetail" class="loading-overlay" aria-label="加载中">
          <div class="loading-card">
            <div class="loading-ring">
              <div class="ring-track"></div>
              <div class="ring-fill" :style="{ '--p': progressLabel + '%' }"></div>
              <div class="ring-center">{{ progressLabel }}%</div>
            </div>
            <div class="cute-loader" aria-hidden="true">
              <div class="blob"></div>
              <div class="shadow"></div>
            </div>
            <div class="loading-text">正在加载书籍详情</div>
            <div class="loading-sub">联网请求可能耗时，请稍候…</div>
          </div>
        </div>

        <div class="left">
          <img class="poster" :src="coverSrc(book.cover_url)" :alt="book.title" />
        </div>

        <div class="right">
          <div class="title">{{ book.title || '（无标题）' }}</div>
          <div class="sub">
            <span class="author">{{ book.author || '作者未知' }}</span>
            <span class="dot">·</span>
            <span v-if="!isCustom" class="rating">豆瓣 {{ formatRating(book.rating) }}</span>

            <span v-if="detailLoadError" class="like-error">{{ detailLoadError }}</span>

            <button
              class="like-btn"
              type="button"
              :class="{ on: liked }"
              :disabled="liking"
              @click.stop="toggleLike"
              :aria-pressed="liked ? 'true' : 'false'"
            >
              <span class="heart" aria-hidden="true">{{ liked ? '♥' : '♡' }}</span>
              <span>{{ liked ? '已喜欢' : '喜欢' }}</span>
            </button>
            <button class="log-btn" type="button" @click.stop="toggleLog">
              读书日志
            </button>
            <button
              class="log-btn"
              type="button"
              :title="isCustom ? '导入你的书籍文件' : '获取全文资源'"
              @click.stop="openReaderSources"
            >
              {{ isCustom ? '导入书籍' : '全文资源' }}
            </button>
            <button
              class="log-btn"
              type="button"
              :disabled="!resumeAssetId || resumeLoading"
              :title="resumeAssetId ? '继续阅读已下载资源' : '暂无已下载资源'"
              @click.stop="continueReading"
            >
              继续阅读
            </button>
            <a
              v-if="taobaoSearchUrl"
              class="log-btn"
              :href="taobaoSearchUrl"
              target="_blank"
              rel="noreferrer"
            >
              淘宝购买
            </a>
            <span v-if="likeError" class="like-error">{{ likeError }}</span>
          </div>

          <div class="tags" v-if="book.tags?.length">
            <span class="tag" v-for="t in book.tags" :key="t">{{ t }}</span>
          </div>
        </div>
      </div>
    </div>

    <main class="content">
      <section class="overview">
        <div class="card summary">
          <h3 class="card-title">内容简介</h3>
          <div class="summary-text">{{ summaryShown || '暂无简介' }}</div>
          <button
            v-if="summaryHasMore"
            class="summary-toggle"
            type="button"
            @click="summaryExpanded = !summaryExpanded"
          >
            {{ summaryExpanded ? '收起' : '展开' }}
          </button>
        </div>

        <div v-if="!isCustom" class="card wordcloud">
          <h3 class="card-title">评论词云</h3>
          <div v-if="wordcloudLoading" class="wc-empty">词云生成中…</div>
          <div v-else-if="wordcloudDataUrl" class="wc-img">
            <img :src="wordcloudDataUrl" alt="wordcloud" />
          </div>
          <div v-else class="wc-empty">
            <button class="ext-btn" type="button" @click="ensureWordcloud">加载词云</button>
            <div v-if="wordcloudError" class="ext-error" style="margin-top:6px">{{ wordcloudError }}</div>
            <div v-else style="margin-top:6px; font-size:12px; opacity:0.75">点击生成，需联网请求豆瓣评论</div>
          </div>
        </div>
      </section>

      <section v-if="logOpen" class="reading-log">
        <div class="card">
          <h3 class="card-title">读书日志</h3>
          <div class="log-editor">
            <textarea
              v-model="logText"
              rows="4"
              maxlength="2000"
              placeholder="写下你对这本书的评价..."
            />
            <div class="log-actions">
              <div class="log-hint">{{ logText.length }}/2000</div>
              <button class="log-submit" type="button" :disabled="logSubmitting" @click="submitLog">
                发布
              </button>
            </div>
            <div v-if="logError" class="log-error">{{ logError }}</div>
          </div>

          <div class="log-list">
            <div v-if="logLoading" class="log-loading">加载中…</div>
            <div v-else-if="!logItems.length" class="log-empty">还没有日志，写下第一条吧。</div>
            <article v-else v-for="it in logItems" :key="it.id" class="log-item">
              <div class="log-time">{{ formatTime(it.created_at) }}</div>
              <div class="log-content">{{ it.content }}</div>
            </article>
          </div>
        </div>
      </section>

      <section v-if="book.title" class="comments">
        <div class="comments-head">
          <h3>书评</h3>
          <div class="source-tabs" role="tablist" aria-label="书评来源">
            <button
              v-if="!isCustom"
              class="tab"
              type="button"
              role="tab"
              :class="{ active: reviewSource === 'douban' }"
              :aria-selected="reviewSource === 'douban' ? 'true' : 'false'"
              @click="selectReviewSource('douban')"
            >
              豆瓣
            </button>
            <button
              class="tab"
              type="button"
              role="tab"
              :class="{ active: reviewSource === 'weibo' }"
              :aria-selected="reviewSource === 'weibo' ? 'true' : 'false'"
              @click="selectReviewSource('weibo')"
            >
              微博
            </button>
            <button
              class="tab"
              type="button"
              role="tab"
              :class="{ active: reviewSource === 'bilibili' }"
              :aria-selected="reviewSource === 'bilibili' ? 'true' : 'false'"
              @click="selectReviewSource('bilibili')"
            >
              B站
            </button>
          </div>
        </div>

        <div v-if="reviewSource === 'douban'">
          <div class="meta" style="margin-bottom: 10px">
            <span v-if="isCustom">自建书籍没有豆瓣短评</span>
            <template v-else>
              <span v-if="loadingComments">加载中...</span>
              <span v-else>第 {{ page }} 页</span>
            </template>
          </div>

          <template v-if="!isCustom">
            <article v-for="c in comments" :key="c.id" class="comment">
              <div class="row">
                <div class="user">{{ c.user || '匿名' }}</div>
                <div class="time">{{ c.time || '' }}</div>
              </div>
              <div class="body">{{ c.content }}</div>
              <div class="foot">
                <span v-if="c.rating != null">评分：{{ c.rating }}</span>
                <span v-if="c.useful != null">有用：{{ c.useful }}</span>
              </div>
            </article>

            <button class="more" @click="loadMore" :disabled="loadingComments">加载更多</button>
          </template>
        </div>

        <div v-else-if="reviewSource === 'weibo'">
          <div class="ext-head" style="margin-bottom: 10px">
            <div class="ext-actions">
              <button class="ext-btn" type="button" :disabled="weiboLoading" @click="refreshWeibo">刷新</button>
              <button class="ext-btn" type="button" :disabled="weiboStatus?.login_running" @click="startWeiboLogin">登录</button>
              <button class="ext-btn" type="button" @click="logoutWeibo">退出</button>
              <span class="ext-meta">
                <span v-if="weiboStatus?.logged_in">已登录</span>
                <span v-else>未登录</span>
              </span>
            </div>
          </div>

          <div v-if="weiboLoading" class="ext-loading">加载中…</div>
          <div v-else-if="weiboError" class="ext-error">{{ weiboError }}</div>
          <div v-else-if="!weiboItems.length" class="ext-empty">暂无结果</div>
          <ul v-else class="ext-list">
            <li v-for="(it, idx) in weiboItems" :key="it.url || idx" class="ext-item">
              <a v-if="it.url" class="ext-title" :href="it.url" target="_blank" rel="noreferrer">{{ it.title || '（无标题）' }}</a>
              <div v-else class="ext-title">{{ it.title || '（无标题）' }}</div>
              <div v-if="it.author" class="ext-sub">{{ it.author }}</div>
              <div v-if="it.text" class="ext-text">{{ truncateText(it.text, 160) }}</div>
            </li>
          </ul>
        </div>

        <div v-else>
          <div class="ext-head" style="margin-bottom: 10px">
            <div class="ext-actions">
              <button class="ext-btn" type="button" :disabled="bilibiliLoading" @click="refreshBilibili">刷新</button>
              <span class="ext-meta">最多 5 篇图文</span>
            </div>
          </div>

          <div v-if="bilibiliLoading" class="ext-loading">加载中…</div>
          <div v-else-if="bilibiliError" class="ext-error">{{ bilibiliError }}</div>
          <div v-else-if="!bilibiliItems.length" class="ext-empty">暂无结果</div>
          <div v-else class="bili-cards">
            <article
              v-for="(it, idx) in bilibiliItems"
              :key="it.url || idx"
              class="bili-card"
              @click="openBilibiliDetail(it)"
            >
              <div class="bili-card-head">
                <div class="bili-card-title">{{ it.title || '（无标题）' }}</div>
                <div class="bili-card-sub">
                  <span v-if="it.author">{{ it.author }}</span>
                  <span v-else>专栏</span>
                  <span v-if="it.url" class="dot">·</span>
                  <a v-if="it.url" class="bili-link" :href="it.url" target="_blank" rel="noreferrer" @click.stop>原文</a>
                </div>
              </div>

              <div class="bili-card-body">
                <div class="bili-excerpt">{{ truncateText(it.text || '', 150) }}</div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { booksAPI } from '../api/books'
import { customBooksAPI } from '../api/customBooks'
import { meAPI } from '../api/me'
import { readerAPI } from '../api/reader'

const route = useRoute()
const router = useRouter()
const bookId = computed(() => route.params.id)
const isCustom = computed(() => String(bookId.value || '').startsWith('custom-'))

const goHome = () => {
  router.push({ name: 'Home' })
}

const openReaderSources = () => {
  router.push({ name: 'ReaderSources', params: { bookId: String(bookId.value) } })
}

const resumeAssetId = ref('')
const resumeLoading = ref(false)

const loadResumeAsset = async () => {
  resumeLoading.value = true
  try {
    const res = await readerAPI.assets(bookId.value)
    if (res.data?.success) {
      const items = res.data.data?.items || []
      resumeAssetId.value = items.length ? String(items[0].id) : ''
    } else {
      resumeAssetId.value = ''
    }
  } catch {
    resumeAssetId.value = ''
  } finally {
    resumeLoading.value = false
  }
}

const continueReading = () => {
  if (!resumeAssetId.value) return
  router.push({ name: 'ReaderView', params: { assetId: String(resumeAssetId.value) } })
}

const fallbackCover =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="480">' +
      '<rect width="100%" height="100%" fill="#f2f3f5"/>' +
      '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#666" font-size="20">No Cover</text>' +
    '</svg>'
  )

const coverSrc = (url) => {
  if (!url) return fallbackCover
  if (url.startsWith('/api/')) {
    if (import.meta.env.DEV) return url
    const apiBase = import.meta.env.VITE_API_BASE || ''
    return `${apiBase}${url}`
  }
  if (url.startsWith('data:')) return url
  if (import.meta.env.DEV) {
    return `/api/books/cover?url=${encodeURIComponent(url)}`
  }
  const apiBase = import.meta.env.VITE_API_BASE || ''
  return `${apiBase}/api/books/cover?url=${encodeURIComponent(url)}`
}

const book = ref({})
const wordcloudDataUrl = ref(null)
const wordcloudLoading = ref(false)
const wordcloudError = ref('')

const loadingDetail = ref(true)
const loadingProgress = ref(0)
const progressLabel = computed(() => {
  const v = Math.round(Math.max(0, Math.min(100, loadingProgress.value || 0)))
  return v
})

const progressTimer = ref(null)

const setProgress = (v) => {
  loadingProgress.value = Math.max(0, Math.min(100, v))
}

const detailLoadError = ref('')

const liked = ref(false)
const liking = ref(false)
const likeError = ref('')

const logOpen = ref(false)
const logText = ref('')
const logItems = ref([])
const logLoading = ref(false)
const logSubmitting = ref(false)
const logError = ref('')

const summaryExpanded = ref(false)
const summaryFull = computed(() => (book.value?.summary || '').toString().trim())
const summaryLimit = 260
const summaryHasMore = computed(() => summaryFull.value.length > summaryLimit)
const summaryShown = computed(() => {
  if (!summaryFull.value) return ''
  if (summaryExpanded.value || !summaryHasMore.value) return summaryFull.value
  return summaryFull.value.slice(0, summaryLimit).trimEnd() + '…'
})

const comments = ref([])
const page = ref(1)
const loadingComments = ref(false)
const commentsLoaded = ref(false)

const reviewSource = ref('douban')

const weiboItems = ref([])
const weiboLoading = ref(false)
const weiboError = ref('')
const weiboStatus = ref(null)
const weiboLoaded = ref(false)

const bilibiliItems = ref([])
const bilibiliLoading = ref(false)
const bilibiliError = ref('')
const bilibiliLoaded = ref(false)

const restoreScrollY = ref(null)

const restoreKey = computed(() => `brs_return_${String(bookId.value || '')}`)

const taobaoSearchUrl = computed(() => {
  const title = (book.value?.title || '').toString().trim()
  if (!title) return ''
  const encoded = encodeURIComponent(title)
  return `https://uland.taobao.com/sem/tbsearch?search_type=item&tab=all&q=${encoded}&keyword=${encoded}`
})

const extractBilibiliCvId = (it) => {
  if (!it) return ''
  const direct = it.cvId || it.cvid || it.article_id || it.articleId || it.id
  if (direct != null && String(direct).trim()) return String(direct).trim()
  const url = (it.url || '').toString()
  const m = url.match(/\bcv(\d+)\b/i)
  if (m) return m[1]
  return ''
}

const openBilibiliDetail = (it) => {
  const cvId = extractBilibiliCvId(it)
  if (cvId) {
    try {
      const payload = {
        scrollY: typeof window !== 'undefined' ? window.scrollY || 0 : 0,
        reviewSource: reviewSource.value,
        ts: Date.now(),
      }
      sessionStorage.setItem(restoreKey.value, JSON.stringify(payload))
    } catch {
      // ignore
    }

    router.push({
      name: 'BilibiliReviewDetail',
      params: { id: String(bookId.value || ''), cvId: String(cvId) },
      query: { from: 'book' },
    })
    return
  }

  if (it?.url) {
    window.open(it.url, '_blank', 'noreferrer')
    return
  }

  bilibiliError.value = '无法识别该专栏的 cvId'
}

const truncateText = (s, maxLen = 140) => {
  const t = (s || '').toString().trim()
  if (!t) return ''
  if (t.length <= maxLen) return t
  return t.slice(0, maxLen).trimEnd() + '…'
}

const buildWeiboQuery = () => {
  const title = (book.value?.title || '').toString().trim()
  if (!title) return ''
  if (isCustom.value) return title
  return `${title} 评价`
}

const buildBilibiliQuery = () => {
  const title = (book.value?.title || '').toString().trim()
  if (!title) return ''
  if (isCustom.value) return title
  return `${title} 书评`
}

const refreshWeiboStatus = async () => {
  try {
    const res = await booksAPI.weiboStatus()
    weiboStatus.value = res.data?.status || null
  } catch {
    weiboStatus.value = null
  }
}

const refreshWeibo = async () => {
  const q = buildWeiboQuery()
  if (!q) return
  weiboLoading.value = true
  weiboError.value = ''
  try {
    await refreshWeiboStatus()
    const res = await booksAPI.weiboSearch(q, 30)
    if (res.data?.success) {
      weiboItems.value = res.data.data || []
    } else {
      weiboItems.value = []
      weiboError.value = res.data?.message || '微博搜索失败'
    }
  } catch (e) {
    weiboItems.value = []
    const status = e?.response?.status
    const msg = e?.response?.data?.message || e?.message || '微博搜索失败'
    if (status === 404) {
      weiboError.value = '微博接口 404：请确认后端已重启并且 /api/books/weibo/search 存在（可访问 /api/debug/routes 自查）'
    } else {
      weiboError.value = msg
    }
  } finally {
    weiboLoading.value = false
  }
}

const startWeiboLogin = async () => {
  try {
    await booksAPI.weiboLogin(false, 240)
    await refreshWeiboStatus()
  } catch (e) {
    const status = e?.response?.status
    const msg = e?.response?.data?.message || e?.message || '微博登录失败'
    if (status === 404) {
      weiboError.value = '微博登录接口 404：请确认后端已重启并且 /api/books/weibo/login 存在（可访问 /api/debug/routes 自查）'
    } else {
      weiboError.value = msg
    }
  }
}

const logoutWeibo = async () => {
  try {
    await booksAPI.weiboLogout()
  } catch {
    // ignore
  } finally {
    await refreshWeiboStatus()
  }
}

const refreshBilibili = async () => {
  const q = buildBilibiliQuery()
  if (!q) return
  bilibiliLoading.value = true
  bilibiliError.value = ''
  try {
    const res = await booksAPI.bilibiliSearch(q, 5)
    if (res.data?.success) {
      bilibiliItems.value = res.data.data || []

      if (restoreScrollY.value != null) {
        const y = Number(restoreScrollY.value) || 0
        restoreScrollY.value = null
        await nextTick()
        try {
          window.scrollTo(0, y)
        } catch {
          // ignore
        }
        try {
          sessionStorage.removeItem(restoreKey.value)
        } catch {
          // ignore
        }
      }
    } else {
      bilibiliItems.value = []
      bilibiliError.value = res.data?.message || 'B站搜索失败'
    }
  } catch (e) {
    bilibiliItems.value = []
    const status = e?.response?.status
    const msg = e?.response?.data?.message || e?.message || 'B站搜索失败'
    if (status === 404) {
      bilibiliError.value = 'B站接口 404：请确认后端已重启并且 /api/books/bilibili/search 存在（可访问 /api/debug/routes 自查）'
    } else {
      bilibiliError.value = msg
    }
  } finally {
    bilibiliLoading.value = false
  }
}

const refreshExternalReviews = async () => {
  await Promise.allSettled([refreshWeiboStatus()])
  await Promise.allSettled([refreshWeibo(), refreshBilibili()])
}

const ensureComments = async () => {
  if (isCustom.value) return
  if (loadingComments.value) return
  if (commentsLoaded.value && comments.value.length) return
  await loadMore()
}

const ensureWeibo = async () => {
  if (weiboLoading.value) return
  if (weiboLoaded.value && weiboItems.value.length) return
  await refreshWeibo()
  weiboLoaded.value = true
}

const ensureBilibili = async () => {
  if (bilibiliLoading.value) return
  if (bilibiliLoaded.value && bilibiliItems.value.length) return
  await refreshBilibili()
  bilibiliLoaded.value = true
}

const ensureWordcloud = async () => {
  if (isCustom.value) return
  if (wordcloudLoading.value || wordcloudDataUrl.value) return
  wordcloudLoading.value = true
  wordcloudError.value = ''
  try {
    const res = await booksAPI.wordcloud(bookId.value, 200)
    if (res.data?.success) {
      wordcloudDataUrl.value = res.data.data?.wordcloud_data_url || ''
    } else {
      wordcloudError.value = res.data?.message || '词云生成失败'
    }
  } catch (e) {
    wordcloudError.value = e?.response?.data?.message || e?.message || '词云生成失败'
  } finally {
    wordcloudLoading.value = false
  }
}

const selectReviewSource = (src) => {
  reviewSource.value = src
}

watch(
  reviewSource,
  (val) => {
    if (val === 'douban') {
      ensureComments()
    } else if (val === 'weibo') {
      ensureWeibo()
    } else if (val === 'bilibili') {
      ensureBilibili()
    }
  },
  { immediate: true }
)

const heroStyle = computed(() => {
  const url = book.value.cover_url || ''
  return url ? { backgroundImage: `url(${coverSrc(url)})` } : {}
})

const init = async () => {
  loadingDetail.value = true
  setProgress(8)
  detailLoadError.value = ''
  try {
    if (isCustom.value) {
      const raw = String(bookId.value || '')
      const customId = raw.replace(/^custom-/, '')
      const res = await customBooksAPI.get(customId)
      if (res.data?.success) {
        book.value = res.data.data.book || {}
        summaryExpanded.value = false
        wordcloudDataUrl.value = null
        comments.value = []
        page.value = 1
        commentsLoaded.value = false
        setProgress(55)
      }
    } else {
      let basicLoaded = false
      try {
        const res = await booksAPI.basic(bookId.value)
        if (res.data?.success) {
          book.value = res.data.data.book || {}
          summaryExpanded.value = false
          wordcloudDataUrl.value = null
          comments.value = []
          page.value = 1
          commentsLoaded.value = false
          setProgress(42)
          basicLoaded = true
        }
      } catch (e) {
        console.warn('basic detail failed, fallback to full detail', e)
      }

      if (!basicLoaded) {
        const res = await booksAPI.detail(bookId.value, 200, 20)
        if (res.data?.success) {
          book.value = res.data.data.book || {}
          summaryExpanded.value = false
          wordcloudDataUrl.value = res.data.data.wordcloud_data_url || null
          comments.value = res.data.data.preview_comments || []
          page.value = 1
          commentsLoaded.value = false
          setProgress(62)

          if (!comments.value.length) {
            await loadMore()
            setProgress(70)
          }
        } else {
          detailLoadError.value = res.data?.message || '详情加载失败'
        }
      }
    }

    try {
      const s = await meAPI.getBookshelfStatus(bookId.value)
      liked.value = !!s.data?.data?.liked
    } catch {
      liked.value = false
    }

    if (book.value?.title) {
      const wantsBilibili = String(route.query?.tab || '') === 'bilibili' || String(route.query?.restore || '') === '1'
      reviewSource.value = wantsBilibili ? 'bilibili' : (isCustom.value ? 'weibo' : 'douban')
      setProgress(isCustom.value ? 65 : 72)
      await refreshExternalReviews()

      if (reviewSource.value === 'douban') {
        await ensureComments()
      } else if (reviewSource.value === 'weibo') {
        await ensureWeibo()
      } else if (reviewSource.value === 'bilibili') {
        await ensureBilibili()
      }
      setProgress(isCustom.value ? 84 : 90)
    }

    await loadResumeAsset()
    setProgress(96)

    likeError.value = ''
  } catch (e) {
    // 保持页面可用：出现网络问题时至少不阻塞后续操作
    console.error('Failed to load book detail:', e)
    const msg =
      e?.response?.data?.message || e?.response?.data?.error || e?.message || '详情加载失败'
    detailLoadError.value = msg
  } finally {
    setProgress(100)
    loadingDetail.value = false
  }
}

const formatRating = (r) => {
  if (r == null) return '暂无'
  if (typeof r === 'number') return r
  if (typeof r === 'string') {
    const s = r.trim()
    if (!s) return '暂无'
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

const toggleLike = async () => {
  if (liking.value) return
  liking.value = true
  likeError.value = ''

  const before = liked.value
  liked.value = !before
  try {
    if (!before) {
      await meAPI.likeBook({
        book_id: bookId.value,
        book_title: book.value.title || '（无标题）',
        book_cover: book.value.cover_url || '',
        book_rating: book.value.rating ?? null,
        book_author: book.value.author || ''
      })
    } else {
      await meAPI.unlikeBook(bookId.value)
    }
  } catch (e) {
    // 回滚 UI
    liked.value = before
    const status = e?.response?.status
    const msg = e?.response?.data?.error || e?.response?.data?.message || e?.message || '操作失败'
    if (status === 404) {
      likeError.value = `喜欢操作失败：接口 404（请确认后端已重启且 /api/me 生效）`
    } else {
      likeError.value = `喜欢操作失败：${msg}`
    }
    console.error('toggleLike failed:', e)
  } finally {
    liking.value = false
  }
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

const loadLogs = async () => {
  logLoading.value = true
  logError.value = ''
  try {
    const res = await meAPI.listBookReadingLogs(bookId.value)
    logItems.value = res.data?.data?.items || []
  } catch (e) {
    const status = e?.response?.status
    if (status === 404) {
      logError.value = `读书日志加载失败：接口 404（请确认后端已重启且 /api/me 生效）`
    } else {
      const msg = e?.response?.data?.error || e?.response?.data?.message || e?.message || '加载失败'
      logError.value = `读书日志加载失败：${msg}`
    }
  } finally {
    logLoading.value = false
  }
}

const toggleLog = async () => {
  logOpen.value = !logOpen.value
  if (logOpen.value) {
    await loadLogs()
  }
}

const submitLog = async () => {
  const content = logText.value.trim()
  if (!content) {
    logError.value = '请输入内容'
    return
  }

  logSubmitting.value = true
  logError.value = ''
  try {
    await meAPI.createReadingLog({
      book_id: bookId.value,
      book_title: book.value.title || '（无标题）',
      content
    })
    logText.value = ''
    await loadLogs()
  } catch (e) {
    const status = e?.response?.status
    if (status === 404) {
      logError.value = `发布失败：接口 404（请确认后端已重启且 /api/me 生效）`
    } else {
      const msg = e?.response?.data?.error || e?.response?.data?.message || e?.message || '发布失败'
      logError.value = `发布失败：${msg}`
    }
  } finally {
    logSubmitting.value = false
  }
}

const loadMore = async () => {
  if (isCustom.value) return
  if (loadingDetail.value) return
  loadingComments.value = true
  try {
    const nextPage = comments.value.length ? page.value + 1 : 1
    const res = await booksAPI.comments(bookId.value, nextPage, 20)
    if (res.data?.success) {
      const items = res.data.data.items || []
      if (items.length) {
        comments.value = comments.value.concat(items)
        page.value = nextPage
      }
    } else {
      detailLoadError.value = res.data?.message || '评论加载失败'
    }
  } catch (e) {
    const msg =
      e?.response?.data?.message || e?.response?.data?.error || e?.message || '评论加载失败'
    detailLoadError.value = msg
  } finally {
    commentsLoaded.value = true
    loadingComments.value = false
  }
}

onMounted(() => {
  // Restore scroll position when user comes back from B站详情页 via fallback navigation.
  if (String(route.query?.restore || '') === '1') {
    try {
      const raw = sessionStorage.getItem(restoreKey.value)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed && typeof parsed === 'object' && parsed.scrollY != null) {
          restoreScrollY.value = parsed.scrollY
        }
      }
    } catch {
      // ignore
    }
  }
  init()
})

watch(
  () => loadingDetail.value,
  (val) => {
    if (val) {
      try {
        if (progressTimer.value) clearInterval(progressTimer.value)
      } catch {
        // ignore
      }
      progressTimer.value = setInterval(() => {
        const current = loadingProgress.value || 0
        if (current < 92) {
          const bump = Math.max(0.5, (100 - current) * 0.04)
          setProgress(current + bump)
        }
      }, 600)
    } else {
      try {
        if (progressTimer.value) clearInterval(progressTimer.value)
      } catch {
        // ignore
      }
      progressTimer.value = null
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.detail {
  min-height: 100vh;
  background: #f6f7fb;
  position: relative;
}


.home-icon {
  position: fixed;
  top: 16px;
  left: 16px;
  z-index: 50;
  width: 34px;
  height: 34px;
  padding: 6px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(10px);
  cursor: pointer;
}

.hero {
  padding: 26px 0;
  background-size: cover;
  background-position: center;
  position: relative;
}

.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  backdrop-filter: blur(18px);
  background: rgba(0, 0, 0, 0.35);
}

.glass {
  position: relative;
  width: min(1100px, 92vw);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 18px;
  padding: 18px;
  align-items: center;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.loading-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.12), rgba(0, 0, 0, 0.52));
  backdrop-filter: blur(12px);
  color: #fff;
}

.loading-card {
  width: min(360px, 86vw);
  padding: 24px 20px 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.22);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.28);
  display: grid;
  gap: 12px;
  justify-items: center;
}

.loading-ring {
  position: relative;
  width: 120px;
  height: 120px;
}

.loading-ring .ring-track,
.loading-ring .ring-fill {
  position: absolute;
  inset: 0;
  border-radius: 50%;
}

.loading-ring .ring-track {
  background: conic-gradient(from 0deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.02));
  filter: drop-shadow(0 8px 18px rgba(0, 0, 0, 0.28));
}

.loading-ring .ring-fill {
  mask: radial-gradient(circle 52% at 50% 50%, transparent 58%, #000 60%);
  background: conic-gradient(from -90deg, #ff9a5f 0%, #ff5e7b var(--p), rgba(255, 255, 255, 0.12) var(--p));
  transition: 0.35s ease;
}

.loading-ring .ring-center {
  position: absolute;
  inset: 18px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.65);
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 22px;
  letter-spacing: 0.4px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.cute-loader {
  position: relative;
  width: 70px;
  height: 56px;
}

.cute-loader .blob {
  position: absolute;
  left: 50%;
  top: 4px;
  width: 44px;
  height: 36px;
  transform: translateX(-50%);
  border-radius: 18px 18px 14px 14px;
  background: rgba(255, 255, 255, 0.92);
  animation: blob-bounce 0.9s ease-in-out infinite;
}

.cute-loader .blob::before,
.cute-loader .blob::after {
  content: '';
  position: absolute;
  top: 14px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.75);
  animation: blob-blink 1.8s infinite;
}

.cute-loader .blob::before {
  left: 13px;
}

.cute-loader .blob::after {
  right: 13px;
}

.cute-loader .shadow {
  position: absolute;
  left: 50%;
  bottom: 6px;
  width: 44px;
  height: 10px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.28);
  filter: blur(1px);
  animation: shadow-pulse 0.9s ease-in-out infinite;
}

@keyframes blob-blink {
  0%,
  20%,
  40%,
  100% {
    transform: scaleY(1);
  }
  30% {
    transform: scaleY(0.25);
  }
}

.loading-text {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

@keyframes blob-bounce {
  0%,
  100% {
    transform: translateX(-50%) translateY(0) scaleX(1);
    border-radius: 18px 18px 14px 14px;
  }
  50% {
    transform: translateX(-50%) translateY(10px) scaleX(1.06);
    border-radius: 16px 16px 18px 18px;
  }
}

@keyframes shadow-pulse {
  0%,
  100% {
    transform: translateX(-50%) scaleX(0.92);
    opacity: 0.8;
  }
  50% {
    transform: translateX(-50%) scaleX(1.12);
    opacity: 0.55;
  }
}

.poster {
  width: 100%;
  border-radius: 14px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.35);
}

.right {
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
}

.title {
  font-size: 38px;
  font-weight: 900;
  line-height: 1.12;
  letter-spacing: 0.4px;
}

.sub {
  opacity: 0.95;
  font-size: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.author {
  font-weight: 700;
  letter-spacing: 0.2px;
}

.dot {
  opacity: 0.7;
}

.rating {
  font-weight: 900;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.22);
}

.like-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-weight: 900;
  cursor: pointer;
  white-space: nowrap;
}

.like-btn .heart {
  font-size: 16px;
  line-height: 1;
}

.like-btn.on .heart {
  color: #ff4d6d;
}

.like-btn.on {
  background: rgba(255, 255, 255, 0.2);
}

.like-btn:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}

.log-btn {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-weight: 900;
  cursor: pointer;
  white-space: nowrap;
}

.log-btn:hover {
  background: rgba(255, 255, 255, 0.18);
}

.like-error {
  font-size: 12px;
  font-weight: 800;
  opacity: 0.95;
}

.reading-log {
  margin-bottom: 14px;
}

.log-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-input {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
}

.log-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.log-hint {
  color: #666;
  font-size: 12px;
  font-weight: 800;
}

.log-submit {
  border: 0;
  background: rgba(0, 0, 0, 0.06);
  color: #111;
  font-weight: 900;
  padding: 10px 14px;
  border-radius: 12px;
  cursor: pointer;
}

.log-submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.log-error {
  color: #b00020;
  font-size: 12px;
  font-weight: 800;
}

.log-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.log-item {
  padding: 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.03);
}

.log-time {
  color: #666;
  font-size: 12px;
  font-weight: 800;
}

.log-content {
  margin-top: 6px;
  white-space: pre-wrap;
  color: #111;
  font-size: 14px;
  line-height: 1.6;
}

.log-loading,
.log-empty {
  color: #666;
  font-size: 13px;
  font-weight: 800;
}

.tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 2px;
}

.tag {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.22);
}

.content {
  width: min(1100px, 92vw);
  margin: 18px auto 40px;
}

.overview {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 14px;
  margin-bottom: 14px;
}

.source-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab {
  appearance: none;
  border: 0;
  background: rgba(0, 0, 0, 0.06);
  color: #111;
  font-weight: 900;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.tab:hover {
  background: rgba(0, 0, 0, 0.08);
}

.tab:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.tab.active {
  background: rgba(17, 17, 17, 0.1);
}

.ext-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ext-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ext-btn {
  appearance: none;
  border: 0;
  background: rgba(0, 0, 0, 0.06);
  color: #111;
  font-weight: 800;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.ext-btn:hover {
  background: rgba(0, 0, 0, 0.08);
}

.ext-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ext-meta {
  font-size: 12px;
  color: #666;
  font-weight: 800;
}

.ext-loading,
.ext-empty {
  color: #666;
  font-size: 13px;
  font-weight: 800;
}

.ext-error {
  color: #c0392b;
  font-size: 13px;
  font-weight: 800;
}

.ext-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}

.ext-item {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.ext-title {
  display: inline-block;
  font-weight: 900;
  color: #111;
  text-decoration: none;
  line-height: 1.35;
}

.ext-title:hover {
  text-decoration: underline;
}

.ext-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
  font-weight: 800;
}

.ext-text {
  margin-top: 6px;
  font-size: 13px;
  color: #333;
  line-height: 1.65;
  white-space: pre-wrap;
}

.bili-cards {
  display: grid;
  gap: 10px;
}

.bili-card {
  padding: 12px;
  border-radius: 14px;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.06);
  cursor: pointer;
}

.bili-card-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bili-card-title {
  font-weight: 900;
  color: #111;
  line-height: 1.35;
}

.bili-card-sub {
  font-size: 12px;
  color: #666;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.bili-card-sub .dot {
  opacity: 0.7;
}

.bili-link {
  color: #111;
  text-decoration: none;
}

.bili-link:hover {
  text-decoration: underline;
}

.bili-card-body {
  margin-top: 10px;
  display: block;
}

.bili-thumb {
  width: 96px;
  height: 72px;
  object-fit: cover;
  border-radius: 10px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.bili-excerpt {
  font-size: 13px;
  color: #333;
  line-height: 1.65;
  white-space: pre-wrap;
}

.bili-full {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.bili-html :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
}

.bili-html :deep(p) {
  margin: 8px 0;
  line-height: 1.75;
}

.bili-html :deep(figure) {
  margin: 10px 0;
}

.card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 16px;
}

.card-title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 900;
  color: #111;
}

.summary-text {
  color: #333;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.summary-toggle {
  margin-top: 10px;
  appearance: none;
  border: 0;
  background: rgba(0, 0, 0, 0.06);
  color: #111;
  font-weight: 800;
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.summary-toggle:hover {
  background: rgba(0, 0, 0, 0.08);
}

.wordcloud .wc-img {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 4px 0;
}

.wordcloud .wc-img img {
  width: 320px;
  max-width: 100%;
  height: 200px;
  object-fit: contain;
  border-radius: 10px;
  background: #fff;
}

.wordcloud .wc-empty {
  opacity: 0.85;
  font-size: 13px;
  color: #666;
}

@media (max-width: 860px) {
  .overview {
    grid-template-columns: 1fr;
  }
}

.comments {
  background: #fff;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 16px;
}

.comments-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.comment {
  padding: 12px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.user {
  font-weight: 800;
}

.time {
  opacity: 0.65;
  font-size: 12px;
}

.body {
  margin-top: 8px;
  white-space: pre-wrap;
  line-height: 1.65;
}

.foot {
  margin-top: 8px;
  opacity: 0.75;
  font-size: 12px;
  display: flex;
  gap: 16px;
}

.more {
  width: 100%;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: #f6f7fb;
  cursor: pointer;
}

.more:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 800px) {
  .glass {
    grid-template-columns: 1fr;
  }

  .poster {
    max-width: 260px;
  }
}
</style>
