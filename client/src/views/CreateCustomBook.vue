<template>
  <div class="page">
    <header class="topbar">
      <div class="left">
        <button class="back" type="button" @click="goBack">返回</button>
        <h2>新增书籍</h2>
      </div>
    </header>

    <main class="content">
      <div class="card">
        <div class="field">
          <label>书名</label>
          <input v-model="title" type="text" placeholder="请输入书名" maxlength="255" />
        </div>

        <div class="field">
          <label>作者</label>
          <input v-model="author" type="text" placeholder="请输入作者" maxlength="255" />
        </div>

        <div class="field">
          <label>封面</label>
          <input type="file" accept="image/*" @change="onPickCover" />
          <div v-if="coverPreview" class="preview">
            <img :src="coverPreview" alt="cover" />
          </div>
        </div>

        <div class="field">
          <label>简介</label>
          <textarea v-model="intro" rows="6" maxlength="5000" placeholder="写一点这本书的简介..." />
          <div class="counter">{{ intro.length }}/5000</div>
        </div>

        <div class="actions">
          <button class="submit" type="button" :disabled="submitting" @click="submit">
            {{ submitting ? '保存中…' : '保存' }}
          </button>
        </div>

        <div v-if="error" class="error">{{ error }}</div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { customBooksAPI } from '../api/customBooks'

const router = useRouter()

const title = ref('')
const author = ref('')
const intro = ref('')
const coverFile = ref(null)
const coverPreview = ref('')
const submitting = ref(false)
const error = ref('')

const onPickCover = (e) => {
  const f = e?.target?.files?.[0]
  coverFile.value = f || null

  if (coverPreview.value) {
    URL.revokeObjectURL(coverPreview.value)
    coverPreview.value = ''
  }

  if (coverFile.value) {
    coverPreview.value = URL.createObjectURL(coverFile.value)
  }
}

onBeforeUnmount(() => {
  if (coverPreview.value) {
    URL.revokeObjectURL(coverPreview.value)
  }
})

const goBack = () => router.back()

const submit = async () => {
  const t = title.value.trim()
  const a = author.value.trim()

  if (!t) {
    error.value = '请输入书名'
    return
  }
  if (!a) {
    error.value = '请输入作者'
    return
  }

  submitting.value = true
  error.value = ''

  try {
    const fd = new FormData()
    fd.append('title', t)
    fd.append('author', a)
    if (intro.value.trim()) fd.append('intro', intro.value.trim())
    if (coverFile.value) fd.append('cover', coverFile.value)

    const res = await customBooksAPI.create(fd)
    const book = res.data?.data?.book
    const bookId = book?.book_id
    if (bookId) {
      router.replace({ name: 'BookDetail', params: { id: String(bookId) } })
    } else {
      router.replace({ name: 'Bookshelf' })
    }
  } catch (e) {
    const msg = e?.response?.data?.error || e?.response?.data?.message || e?.message || '保存失败'
    error.value = String(msg)
  } finally {
    submitting.value = false
  }
}
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

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

label {
  font-weight: 900;
  color: #111;
  font-size: 13px;
}

input[type='text'],
textarea {
  border: 1px solid rgba(0, 0, 0, 0.10);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.75);
  outline: none;
}

.preview {
  margin-top: 10px;
  width: min(260px, 60vw);
  aspect-ratio: 3 / 4;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.6);
}

.preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.counter {
  text-align: right;
  color: #666;
  font-size: 12px;
  font-weight: 800;
}

.actions {
  display: flex;
  justify-content: flex-end;
}

.submit {
  border: 0;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 900;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.06);
}

.submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.error {
  margin-top: 10px;
  color: #b00020;
  font-weight: 900;
  font-size: 13px;
}
</style>
