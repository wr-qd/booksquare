<template>
  <div class="page" :style="pageBgStyle">
    <header class="topbar">
      <div class="left">
        <button class="back" type="button" @click="goBack">返回</button>
        <h2 class="h">阅读</h2>
      </div>
      <div class="right" v-if="asset">
        <span class="fmt">{{ (asset.format || '').toUpperCase() }}</span>
      </div>
    </header>

    <div class="font-dock" tabindex="0">
      <div class="dock-tab">调节</div>
      <div class="dock-body">
        <div class="dock-title">阅读调节</div>
        <div class="dock-section">
          <div class="font-label">字号</div>
          <div class="dock-row">
            <button type="button" class="font-btn" @click="incFont" :disabled="fontSize >= MAX_FONT">A+</button>
            <div class="font-size">{{ fontSize }}px</div>
            <button type="button" class="font-btn" @click="decFont" :disabled="fontSize <= MIN_FONT">A-</button>
            <button type="button" class="font-reset" @click="resetFont">重置</button>
          </div>
        </div>

        <div class="dock-section">
          <div class="font-label">背景</div>
          <div class="dock-row wrap">
            <button type="button" class="font-btn" @click="triggerBgUpload">上传图片</button>
            <button type="button" class="font-btn" @click="setBgColor('#f7f5f0')">浅色</button>
            <button type="button" class="font-btn" @click="setBgGradient('linear-gradient(135deg, #dfe9f3 0%, #ffffff 100%)')">渐变</button>
            <button type="button" class="font-reset" @click="setBgDefault">默认</button>
          </div>
          <div class="dock-row">
            <label class="overlay-label">遮罩 {{ (bgOverlay * 100) | 0 }}%</label>
            <input
              class="overlay-slider"
              type="range"
              min="0"
              max="0.6"
              step="0.05"
              :value="bgOverlay"
              @input="(e) => setBgOverlay(e?.target?.value)"
            />
          </div>
          <input ref="bgFileInput" type="file" accept="image/*" class="hidden-input" @change="onBgFileChange" />
        </div>
      </div>
    </div>

    <main class="content">
      <div v-if="loading" class="hint">加载中…</div>
      <div v-else-if="error" class="hint error">{{ error }}</div>

      <div v-else class="card">
        <div class="meta">
          <div class="title">{{ asset.title }}</div>
          <div class="author">{{ asset.author || '作者未知' }}</div>
        </div>

        <div v-if="asset.format === 'txt'" class="reader txt-mode" @mouseup="onTextMouseUp">
          <pre class="txt" :style="{ fontSize: fontSize + 'px' }">{{ text }}</pre>

          <div
            v-if="selection.visible"
            class="selection-pop"
            :style="{ top: selection.y + 'px', left: selection.x + 'px' }"
          >
            <button type="button" class="pop-btn" @click="openNoteDialog('note')">加入随笔</button>
            <button type="button" class="pop-btn" @click="saveQuote">收藏句子</button>
            <span v-if="noteSuccess" class="pop-msg">{{ noteSuccess }}</span>
            <span v-if="noteError && !noteDialog" class="pop-msg error">{{ noteError }}</span>
          </div>

          <div
            v-if="noteDialog"
            class="note-pop"
            :style="{ top: noteAnchor.y + 'px', left: noteAnchor.x + 'px' }"
          >
            <div class="note-head">
              <div class="note-title">加入随笔</div>
              <button class="note-close" type="button" @click="closeNoteDialog">×</button>
            </div>
            <div class="note-quote" v-if="quotePreview">“{{ quotePreview }}”</div>
            <textarea
              v-model="noteContent"
              rows="3"
              maxlength="2000"
              placeholder="写下你的想法..."
            ></textarea>
            <div class="note-actions">
              <span class="note-hint">{{ noteContent.length }}/2000</span>
              <button class="note-save" type="button" :disabled="noteSaving" @click="saveNote">
                {{ noteSaving ? '保存中…' : '保存' }}
              </button>
            </div>
            <div v-if="noteError" class="note-error">{{ noteError }}</div>
          </div>
        </div>

        <div v-else-if="asset.format === 'epub'" class="reader">
          <div class="epub-actions">
            <button class="nav" type="button" @click="prevPage">上一页</button>
            <button class="nav" type="button" @click="nextPage">下一页</button>
          </div>
          <div ref="epubEl" class="epub"></div>
        </div>

        <div v-else class="hint">
          暂不支持该格式的站内阅读（当前：{{ asset.format }}）
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { readerAPI } from '../api/reader'
import { meAPI } from '../api/me'
import ePub from 'epubjs'

const route = useRoute()
const router = useRouter()

const assetId = String(route.params.assetId || '')

const loading = ref(true)
const error = ref('')
const asset = ref(null)
const text = ref('')

const selection = ref({ text: '', x: 0, y: 0, visible: false })
const noteDialog = ref(false)
const noteContent = ref('')
const noteSaving = ref(false)
const noteError = ref('')
const noteSuccess = ref('')
const noteAnchor = ref({ x: 0, y: 0 })
const quotePreview = ref('')
const fontSize = ref(15)
const bgMode = ref('default') // default | image | color | gradient
const bgValue = ref('')
const bgOverlay = ref(0.12)
const bgFileInput = ref(null)

const savedTxtScrollY = ref(0)
const savedEpubCfi = ref('')

const epubEl = ref(null)
let epubBook = null
let epubRendition = null

let scrollTimer = null
let epubTimer = null
let pendingTxtScrollY = null
let pendingEpubCfi = ''

const getScrollY = () => {
  if (typeof window === 'undefined') return 0
  return window.scrollY || document.documentElement?.scrollTop || 0
}

const setScrollY = (y) => {
  try {
    window.scrollTo({ top: y, left: 0, behavior: 'auto' })
  } catch {
    // ignore
  }
}

const flushProgress = () => {
  // Save current positions immediately; best-effort, ignore errors.
  if (asset.value?.format === 'txt') {
    const y = pendingTxtScrollY != null ? pendingTxtScrollY : (typeof window !== 'undefined' ? window.scrollY || 0 : 0)
    if (y != null) {
      readerAPI.setProgress(assetId, { kind: 'txt', scrollY: y }).catch(() => {})
      pendingTxtScrollY = null
    }
  }

  if (asset.value?.format === 'epub') {
    let cfi = pendingEpubCfi
    try {
      const loc = epubRendition?.currentLocation?.()
      cfi = cfi || loc?.start?.cfi || ''
    } catch {
      // ignore
    }
    if (cfi) {
      readerAPI.setProgress(assetId, { kind: 'epub', cfi }).catch(() => {})
      pendingEpubCfi = ''
    }
  }
}

const goBack = () => router.back()

const FONT_KEY = 'reader_font_size'
const MIN_FONT = 12
const MAX_FONT = 26
const BG_KEY = 'reader_bg_pref'
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

const applyEpubFontSize = (sizePx) => {
  try {
    if (epubRendition?.themes?.fontSize) {
      epubRendition.themes.fontSize(`${sizePx}px`)
    }
  } catch {
    // ignore
  }
}

const setFontSize = (val) => {
  const clamped = Math.min(MAX_FONT, Math.max(MIN_FONT, Math.round(val)))
  fontSize.value = clamped
  try {
    localStorage.setItem(FONT_KEY, String(clamped))
  } catch {
    // ignore
  }
  applyEpubFontSize(clamped)
}

const incFont = () => setFontSize(fontSize.value + 1)
const decFont = () => setFontSize(fontSize.value - 1)
const resetFont = () => setFontSize(15)

const saveBgPref = () => {
  try {
    const payload = {
      mode: bgMode.value,
      value: bgValue.value,
      overlay: bgOverlay.value
    }
    localStorage.setItem(BG_KEY, JSON.stringify(payload))
  } catch {
    // ignore
  }
}

const loadBgPref = () => {
  try {
    const raw = localStorage.getItem(BG_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (parsed?.mode) bgMode.value = parsed.mode
    if (typeof parsed?.value === 'string') bgValue.value = parsed.value
    if (typeof parsed?.overlay === 'number') bgOverlay.value = clamp(parsed.overlay, 0, 0.8)
  } catch {
    // ignore
  }
}

const setBgDefault = () => {
  bgMode.value = 'default'
  bgValue.value = ''
  bgOverlay.value = 0.12
  saveBgPref()
}

const setBgColor = (color = '#f7f5f0') => {
  bgMode.value = 'color'
  bgValue.value = color
  saveBgPref()
}

const setBgGradient = (gradient = 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)') => {
  bgMode.value = 'gradient'
  bgValue.value = gradient
  saveBgPref()
}

const setBgOverlay = (val) => {
  bgOverlay.value = clamp(Number(val), 0, 0.8)
  saveBgPref()
}

const triggerBgUpload = () => {
  bgFileInput.value?.click()
}

const onBgFileChange = (e) => {
  const file = e?.target?.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    bgMode.value = 'image'
    bgValue.value = reader.result || ''
    saveBgPref()
  }
  reader.readAsDataURL(file)
  // allow same file pick next time
  if (e?.target) e.target.value = ''
}

const pageBgStyle = computed(() => {
  const overlay = `rgba(0, 0, 0, ${bgOverlay.value})`
  const overlayLayer = `linear-gradient(${overlay}, ${overlay})`

  if (bgMode.value === 'image' && bgValue.value) {
    return {
      backgroundImage: `${overlayLayer}, url('${bgValue.value}')`,
      backgroundSize: 'cover',
      backgroundRepeat: 'no-repeat',
      backgroundAttachment: 'fixed',
      backgroundPosition: 'center center'
    }
  }

  if (bgMode.value === 'gradient' && bgValue.value) {
    return {
      backgroundImage: `${overlayLayer}, ${bgValue.value}`,
      backgroundAttachment: 'fixed',
      backgroundSize: 'cover',
      backgroundRepeat: 'no-repeat'
    }
  }

  if (bgMode.value === 'color' && bgValue.value) {
    return {
      backgroundColor: bgValue.value,
      backgroundImage: overlayLayer,
      backgroundAttachment: 'fixed'
    }
  }

  return {
    backgroundColor: 'transparent'
  }
})

const onTextMouseUp = (evt) => {
  if (asset.value?.format !== 'txt') return
  if (evt?.target?.closest('.selection-pop') || evt?.target?.closest('.note-pop')) return
  const sel = window.getSelection ? window.getSelection() : null
  const raw = sel ? sel.toString() : ''
  const picked = (raw || '').trim()
  if (!picked || picked.length < 2) {
    selection.value = { text: '', x: 0, y: 0, visible: false }
    return
  }

  let rect = null
  try {
    if (sel && sel.rangeCount > 0) {
      rect = sel.getRangeAt(0).getBoundingClientRect()
    }
  } catch {
    rect = null
  }

  const baseX = rect ? rect.left + rect.width / 2 : evt?.clientX || 0
  const baseY = rect ? rect.top : evt?.clientY || 0

  let offsetX = 0
  let offsetY = 0
  try {
    const host = evt?.currentTarget?.getBoundingClientRect?.()
    offsetX = (host?.left || 0) + (typeof window !== 'undefined' ? window.scrollX || 0 : 0)
    offsetY = (host?.top || 0) + (typeof window !== 'undefined' ? window.scrollY || 0 : 0)
  } catch {
    offsetX = 0
    offsetY = 0
  }

  const pageX = (baseX || 0) + (typeof window !== 'undefined' ? window.scrollX || 0 : 0)
  const pageY = (baseY || 0) + (typeof window !== 'undefined' ? window.scrollY || 0 : 0)

  selection.value = {
    text: picked,
    x: pageX - offsetX,
    y: pageY - offsetY - 6,
    visible: true
  }
}

const closeNoteDialog = () => {
  noteDialog.value = false
  noteContent.value = ''
  noteError.value = ''
  noteSuccess.value = ''
  quotePreview.value = ''
}

const openNoteDialog = (kind = 'note') => {
  if (!selection.value.text) return
  noteContent.value = ''
  quotePreview.value = selection.value.text
  noteAnchor.value = { x: selection.value.x, y: selection.value.y + 14 }
  noteError.value = ''
  if (kind === 'note') {
    noteDialog.value = true
  }
}

const ensureBookMeta = () => {
  const bookId = asset.value?.book_id
  const bookTitle = asset.value?.title || asset.value?.book_title || ''
  return {
    bookId,
    bookTitle: bookTitle || '（无标题）'
  }
}

const saveNote = async () => {
  const picked = quotePreview.value || selection.value.text
  if (!picked) return
  const { bookId, bookTitle } = ensureBookMeta()
  if (!bookId) {
    noteError.value = '缺少书籍信息，无法保存'
    return
  }
  noteSaving.value = true
  noteError.value = ''
  try {
    const res = await meAPI.createNote({
      book_id: bookId,
      book_title: bookTitle,
      asset_id: asset.value?.id || null,
      kind: 'note',
      quote_text: quotePreview.value || selection.value.text,
      content: noteContent.value
    })
    if (res.data?.success) {
      noteSuccess.value = '已保存随笔'
      setTimeout(() => {
        noteSuccess.value = ''
      }, 1200)
      closeNoteDialog()
      selection.value = { text: '', x: 0, y: 0, visible: false }
    } else {
      noteError.value = res.data?.message || '保存失败'
    }
  } catch (e) {
    noteError.value = e?.response?.data?.message || e?.message || '保存失败'
  } finally {
    noteSaving.value = false
  }
}

const saveQuote = async () => {
  if (!selection.value.text) return
  const { bookId, bookTitle } = ensureBookMeta()
  if (!bookId) return
  noteError.value = ''
  noteSaving.value = true
  try {
    const res = await meAPI.createNote({
      book_id: bookId,
      book_title: bookTitle,
      asset_id: asset.value?.id || null,
      kind: 'quote',
      quote_text: selection.value.text
    })
    if (res.data?.success) {
      noteSuccess.value = '已收藏'
      setTimeout(() => {
        noteSuccess.value = ''
      }, 1200)
      selection.value = { text: '', x: 0, y: 0, visible: false }
      closeNoteDialog()
    } else {
      noteError.value = res.data?.message || '收藏失败'
    }
  } catch (e) {
    noteError.value = e?.response?.data?.message || e?.message || '收藏失败'
  } finally {
    noteSaving.value = false
  }
}

const cleanupEpub = () => {
  try {
    epubRendition?.destroy?.()
  } catch {
    // ignore
  }
  epubRendition = null

  try {
    epubBook?.destroy?.()
  } catch {
    // ignore
  }
  epubBook = null
}

const loadProgress = async () => {
  try {
    const res = await readerAPI.progress(assetId)
    if (res.data?.success) {
      const p = res.data.data?.progress || {}
      savedTxtScrollY.value = Number(p.txt?.scrollY || 0)
      savedEpubCfi.value = String(p.epub?.cfi || '')
    }
  } catch {
    // ignore
  }
}

const saveTxtProgress = (scrollY) => {
  if (scrollTimer) clearTimeout(scrollTimer)
  pendingTxtScrollY = scrollY
  scrollTimer = setTimeout(() => {
    readerAPI.setProgress(assetId, { kind: 'txt', scrollY: pendingTxtScrollY }).catch(() => {})
    pendingTxtScrollY = null
  }, 600)
}

const saveEpubProgress = (cfi) => {
  if (!cfi) return
  if (epubTimer) clearTimeout(epubTimer)
  pendingEpubCfi = cfi
  epubTimer = setTimeout(() => {
    readerAPI.setProgress(assetId, { kind: 'epub', cfi: pendingEpubCfi }).catch(() => {})
    pendingEpubCfi = ''
  }, 600)
}

const onWindowScroll = () => {
  if (asset.value?.format !== 'txt') return
  saveTxtProgress(getScrollY())
  // Hide selection toolbar when scrolling
  selection.value = { text: '', x: 0, y: 0, visible: false }
}

const nextPage = () => {
  try {
    epubRendition?.next()
  } catch {
    // ignore
  }
}

const prevPage = () => {
  try {
    epubRendition?.prev()
  } catch {
    // ignore
  }
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const meta = await readerAPI.assetMeta(assetId)
    if (!meta.data?.success) {
      error.value = meta.data?.message || '读取资源失败'
      return
    }

    asset.value = meta.data.data?.asset

    await loadProgress()
    loadBgPref()

    try {
      const savedFont = Number(localStorage.getItem(FONT_KEY) || '')
      if (!Number.isNaN(savedFont) && savedFont >= MIN_FONT && savedFont <= MAX_FONT) {
        fontSize.value = savedFont
      }
    } catch {
      // ignore
    }

    if (asset.value?.format === 'txt') {
      const res = await readerAPI.assetText(assetId)
      text.value = res.data || ''

      await nextTick()
      if (savedTxtScrollY.value > 0) {
        // Two-pass restore to out-race router scrollBehavior
        setScrollY(savedTxtScrollY.value)
        setTimeout(() => setScrollY(savedTxtScrollY.value), 50)
      }
    } else if (asset.value?.format === 'epub') {
      cleanupEpub()

      const res = await readerAPI.assetBinary(assetId)
      const buf = res.data

      epubBook = ePub(buf)
      epubRendition = epubBook.renderTo(epubEl.value, {
        width: '100%',
        height: '100%'
      })

      applyEpubFontSize(fontSize.value)

      epubRendition.on('relocated', (location) => {
        try {
          const cfi = location?.start?.cfi
          if (cfi) saveEpubProgress(cfi)
        } catch {
          // ignore
        }
      })

      const cfi = savedEpubCfi.value
      if (cfi) {
        await epubRendition.display(cfi)
      } else {
        await epubRendition.display()
      }
    }
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || '读取资源失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('scroll', onWindowScroll, { passive: true })
  window.addEventListener('beforeunload', flushProgress)
  load()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onWindowScroll)
  window.removeEventListener('beforeunload', flushProgress)
  if (scrollTimer) {
    clearTimeout(scrollTimer)
  }
  if (epubTimer) {
    clearTimeout(epubTimer)
  }
  flushProgress()
  cleanupEpub()
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
}

.left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.h {
  margin: 0;
}

.right {
  display: flex;
  align-items: center;
}

.fmt {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.70);
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: var(--ink-soft);
}

.back {
  border: 1px solid rgba(0, 0, 0, 0.10);
  background: rgba(255, 255, 255, 0.70);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--ink);
}

.content {
  padding: 18px;
  max-width: 980px;
  margin: 0 auto;
  position: relative;
}

.hint {
  color: var(--ink-soft);
}

.hint.error {
  color: #c33;
}

.card {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.60);
  border-radius: 16px;
  box-shadow: var(--glass-shadow);
  padding: 16px;
  position: relative;
}

.meta {
  margin-bottom: 14px;
}

.title {
  font-size: 18px;
  font-weight: 900;
  color: var(--ink);
}

.author {
  margin-top: 4px;
  color: var(--ink-soft);
}

.txt {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
  color: var(--ink);
}
.font-dock {
  position: fixed;
  right: 18px;
  top: 140px;
  display: grid;
  grid-template-columns: auto;
  gap: 0;
  padding: 6px;
  background: transparent;
  z-index: 12;
  outline: none;
}

.dock-tab {
  background: rgba(16, 24, 40, 0.72);
  color: #f8fafc;
  padding: 10px 8px;
  border-radius: 12px 0 0 12px;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}

.font-dock .dock-title {
  font-weight: 900;
  color: #f8fafc;
  text-align: center;
}

.font-dock .dock-section {
  display: grid;
  gap: 6px;
  background: rgba(255, 255, 255, 0.03);
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.font-dock .font-label {
  font-weight: 800;
  color: #e5e7eb;
}

.font-dock .font-size {
  color: #e5e7eb;
  font-weight: 800;
  text-align: center;
}

.font-dock .dock-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dock-row.wrap {
  flex-wrap: wrap;
}

.font-dock .font-btn,
.font-dock .font-reset {
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  padding: 6px 10px;
  border-radius: 10px;
  font-weight: 800;
  cursor: pointer;
  color: #f8fafc;
}

.font-dock .font-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.font-dock .font-reset {
  background: rgba(59, 130, 246, 0.14);
  border-color: rgba(59, 130, 246, 0.3);
}

.overlay-label {
  color: #e5e7eb;
  font-size: 12px;
  min-width: 72px;
}

.overlay-slider {
  flex: 1;
}

.dock-body {
  display: none;
  grid-template-columns: 1fr;
  gap: 10px;
  padding: 14px;
  margin-top: 8px;
  background: rgba(16, 24, 40, 0.86);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.25);
}

.font-dock:hover .dock-body,
.font-dock:focus-within .dock-body {
  display: grid;
}

.font-dock:hover {
  padding: 6px 6px 6px 12px;
}

@media (max-width: 768px) {
  .font-dock {
    top: auto;
    bottom: 16px;
    right: 12px;
    grid-auto-flow: row;
  }
}

.selection-pop {
  position: absolute;
  transform: translate(-50%, -80%);
  background: rgba(16, 24, 40, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  display: flex;
  gap: 6px;
  padding: 8px;
  z-index: 8;
  align-items: center;
}

.selection-pop .pop-btn {
  background: #ff7a45;
  color: #fff;
  border: none;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s ease;
}

.selection-pop .pop-btn:hover {
  background: #ff925f;
}

.pop-msg {
  font-size: 12px;
  color: #d1f7c4;
}

.pop-msg.error {
  color: #fca5a5;
}

.note-pop {
  position: absolute;
  transform: translate(-50%, 0);
  width: min(380px, 92vw);
  background: #101623;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  padding: 14px;
  box-shadow: 0 18px 36px rgba(0, 0, 0, 0.4);
  color: #f5f5f5;
  display: grid;
  gap: 10px;
  z-index: 9;
}

.note-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.note-title {
  font-weight: 700;
  font-size: 16px;
}

.note-close {
  background: transparent;
  border: none;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
}

.note-quote {
  font-size: 14px;
  opacity: 0.82;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.note-card textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.28);
  color: #f5f5f5;
  padding: 10px;
  resize: vertical;
}

.note-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.note-hint {
  font-size: 12px;
  opacity: 0.7;
}

.note-save {
  background: #3b82f6;
  color: #fff;
  border: none;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  min-width: 90px;
}

.note-error {
  color: #ffb4b4;
  font-size: 12px;
}

.epub-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.nav {
  border: 1px solid rgba(0, 0, 0, 0.10);
  background: rgba(255, 255, 255, 0.70);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--ink);
}

.epub {
  height: calc(100vh - 240px);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.55);
}
</style>
