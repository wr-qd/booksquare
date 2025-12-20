<template>
  <div class="page">
    <header class="topbar">
      <div class="left">
        <button class="back" type="button" @click="goBack">返回</button>
        <h2>{{ isCustom ? '导入书籍' : '全文资源' }}</h2>
      </div>
    </header>

    <main class="content">
      <div v-if="loading" class="hint">{{ isCustom ? '加载中…' : '正在查找可用资源…' }}</div>
      <div v-else-if="error" class="hint error">{{ error }}</div>

      <div v-else class="card">
        <div class="meta">
          <div class="title">{{ book.title || '（无标题）' }}</div>
          <div class="author">{{ book.author || '作者未知' }}</div>
          <div class="sub">{{ isCustom ? '自建书籍仅支持本地导入与已导入资源' : '仅展示白名单来源（合规可用）。' }}</div>
        </div>

        <section class="import">
          <div class="sec-head">
            <div class="sec-title">本地导入</div>
            <div class="sec-sub">支持 TXT / EPUB，本地读取不抓取外网。</div>
          </div>
          <div class="import-row">
            <input class="file" type="file" accept=".txt,.epub" @change="onPick" />
            <button class="btn primary" type="button" :disabled="uploading || !picked" @click="doUpload">
              {{ uploading ? '导入中…' : '导入并阅读' }}
            </button>
          </div>
        </section>

        <section v-if="assets.length" class="downloaded">
          <div class="sec-head">
            <div class="sec-title">已导入</div>
            <div class="sec-sub">随时继续阅读或重新打开。</div>
          </div>
          <div class="dl-list">
            <div v-for="a in assets" :key="a.id" class="dl-item">
              <div class="dl-main">
                <div class="dl-name">{{ a.title }}</div>
                <div class="dl-sub">{{ (a.format || '').toUpperCase() }} · {{ a.source }}</div>
              </div>
              <button class="btn" type="button" @click="openAsset(a)">继续阅读</button>
            </div>
          </div>
        </section>

        <section v-if="!isCustom">
          <div v-if="!items.length" class="empty">暂未找到可用资源（可能该书不在该来源收录）。</div>

          <div v-else class="list">
            <article v-for="it in items" :key="it.source + ':' + it.source_id" class="item">
              <div class="it-title">{{ it.title }}</div>
              <div class="it-author">{{ it.author || '作者未知' }}</div>
              <div class="actions">
                <button
                  v-for="d in it.downloads"
                  :key="d.format + ':' + d.url"
                  class="btn"
                  type="button"
                  :disabled="downloading"
                  @click="download(it, d)"
                >
                  下载并阅读（{{ d.format.toUpperCase() }}）
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { readerAPI } from '../api/reader'
import { customBooksAPI } from '../api/customBooks'

const route = useRoute()
const router = useRouter()

const bookId = String(route.params.bookId || '')
const isCustom = computed(() => bookId.startsWith('custom-'))
const customId = computed(() => bookId.replace(/^custom-/, ''))

const loading = ref(true)
const downloading = ref(false)
const error = ref('')
const book = ref({ title: '', author: '' })
const items = ref([])
const assets = ref([])
const picked = ref(null)
const uploading = ref(false)

const goBack = () => router.back()

const loadCustomBook = async () => {
  try {
    const res = await customBooksAPI.get(customId.value)
    if (res.data?.success) {
      book.value = res.data.data?.book || {}
    }
  } catch {
    // ignore; fallback to empty book info
  }
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    if (isCustom.value) {
      await loadCustomBook()
      await loadAssets()
    } else {
      const res = await readerAPI.sources(bookId)
      if (res.data?.success) {
        book.value = res.data.data?.book || {}
        const src = (res.data.data?.sources || [])[0]
        items.value = src?.items || []
        await loadAssets()
      } else {
        error.value = res.data?.message || '获取资源失败'
      }
    }
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || '获取资源失败'
  } finally {
    loading.value = false
  }
}

const loadAssets = async () => {
  try {
    const res = await readerAPI.assets(bookId)
    if (res.data?.success) {
      assets.value = res.data.data?.items || []
    }
  } catch {
    // ignore
  }
}

const openAsset = (a) => {
  router.push({ name: 'ReaderView', params: { assetId: String(a.id) } })
}

const onPick = (e) => {
  const f = e?.target?.files?.[0]
  picked.value = f || null
}

const doUpload = async () => {
  if (!picked.value) return
  uploading.value = true
  error.value = ''
  try {
    const res = await readerAPI.upload({
      bookId,
      file: picked.value,
      title: picked.value.name
    })

    if (res.data?.success) {
      const assetId = res.data.data?.asset?.id
      await loadAssets()
      picked.value = null
      if (assetId) {
        router.push({ name: 'ReaderView', params: { assetId: String(assetId) } })
      }
    } else {
      error.value = res.data?.message || '导入失败'
    }
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || '导入失败'
  } finally {
    uploading.value = false
  }
}

const download = async (it, d) => {
  downloading.value = true
  error.value = ''
  try {
    const res = await readerAPI.download({
      book_id: bookId,
      source: it.source,
      source_id: it.source_id,
      title: it.title,
      author: it.author,
      format: d.format,
      url: d.url
    })

    if (res.data?.success) {
      const assetId = res.data.data?.asset?.id
      if (assetId) {
        await loadAssets()
        router.push({ name: 'ReaderView', params: { assetId: String(assetId) } })
        return
      }
      error.value = '下载成功，但缺少资源ID'
    } else {
      error.value = res.data?.message || '下载失败'
    }
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || '下载失败'
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 20% 20%, rgba(64, 95, 255, 0.06), transparent 35%),
    radial-gradient(circle at 80% 0%, rgba(255, 137, 95, 0.08), transparent 32%),
    #f7f8fc;
}

.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
}

.left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back {
  border: 1px solid rgba(0, 0, 0, 0.10);
  background: rgba(255, 255, 255, 0.85);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--ink);
  font-weight: 800;
}

.content {
  padding: 18px;
  max-width: 1020px;
  margin: 0 auto;
}

.hint {
  color: var(--ink-soft);
}

.hint.error {
  color: #c33;
}

.card {
  background: #fff;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.08);
  padding: 18px;
}

.meta {
  margin-bottom: 12px;
  display: grid;
  gap: 4px;
}

.title {
  font-size: 20px;
  font-weight: 900;
  color: #0f172a;
}

.author {
  margin-top: 4px;
  color: #475569;
}

.sub {
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.empty {
  margin-top: 10px;
  color: var(--ink-soft);
}

.downloaded {
  margin: 10px 0 14px;
}

.import {
  margin: 12px 0 16px;
}

.sec-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.sec-title {
  font-weight: 900;
  color: #0f172a;
  margin-bottom: 8px;
  font-size: 14px;
}

.sec-sub {
  font-size: 12px;
  color: #94a3b8;
}

.import-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.file {
  border: 1px solid rgba(0, 0, 0, 0.10);
  background: rgba(255, 255, 255, 0.90);
  border-radius: 10px;
  padding: 8px 10px;
  color: var(--ink);
  min-width: 240px;
}

.dl-list {
  display: grid;
  gap: 10px;
}

.dl-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  border-radius: 14px;
  background: #f8fafc;
}

.dl-name {
  font-weight: 900;
  color: var(--ink);
}

.dl-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-soft);
}

.list {
  display: grid;
  gap: 12px;
}

.item {
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: 14px;
  padding: 12px;
  background: #f8fafc;
}

.it-title {
  font-weight: 900;
  color: var(--ink);
}

.it-author {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ink-soft);
}

.actions {
  margin-top: 10px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn {
  border: 1px solid rgba(0, 0, 0, 0.10);
  background: rgba(255, 255, 255, 0.90);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--ink);
  font-weight: 800;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.primary {
  background: #0f172a;
  color: #fff;
  border-color: #0f172a;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.18);
}
</style>
