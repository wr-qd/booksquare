<template>
  <div class="auth-container">
    <div class="auth-card">
      <h1 class="auth-title">{{ isLogin ? '登录' : '注册' }}</h1>
      
      <form @submit.prevent="handleSubmit" class="auth-form">
        <!-- 邮箱 -->
        <div class="form-group">
          <label for="email">邮箱</label>
          <input
            id="email"
            v-model="formData.email"
            type="email"
            placeholder="请输入邮箱"
            required
          />
        </div>

        <!-- 用户名（仅注册） -->
        <div v-if="!isLogin" class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="formData.username"
            type="text"
            placeholder="请输入用户名"
            required
          />
        </div>

        <!-- 密码 -->
        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="formData.password"
            type="password"
            placeholder="请输入密码"
            required
          />
        </div>

        <!-- 验证码已取消，直接注册 -->

        <!-- 错误提示 -->
        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <!-- 成功提示 -->
        <div v-if="success" class="success-message">
          {{ success }}
        </div>

        <!-- 提交按钮 -->
        <button type="submit" :disabled="loading" class="submit-btn">
          {{ loading ? '处理中...' : (isLogin ? '登录' : '注册') }}
        </button>
      </form>

      <!-- 切换登录/注册 -->
      <div class="auth-switch">
        <span v-if="isLogin">
          还没有账号？
          <a @click="isLogin = false" href="javascript:;">立即注册</a>
        </span>
        <span v-else>
          已有账号？
          <a @click="isLogin = true" href="javascript:;">立即登录</a>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '../api/auth'

const router = useRouter()
const isLogin = ref(true)
const loading = ref(false)
const error = ref('')
const success = ref('')

const formData = reactive({
  email: '',
  username: '',
  password: ''
})

// 提交表单
const handleSubmit = async () => {
  error.value = ''
  success.value = ''
  loading.value = true

  try {
    if (isLogin.value) {
      // 登录
      const response = await authAPI.login(formData.email, formData.password)
      
      // 保存token和用户信息
      localStorage.setItem('token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      
      success.value = '登录成功，正在跳转...'
      setTimeout(() => {
        router.push('/')
      }, 1000)
    } else {
      // 注册（无需验证码）
      const response = await authAPI.register(
        formData.email,
        formData.username,
        formData.password
      )
      
      // 保存token和用户信息
      localStorage.setItem('token', response.data.token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      
      success.value = '注册成功，正在跳转...'
      setTimeout(() => {
        router.push('/')
      }, 1000)
    }
  } catch (err) {
    error.value = err.response?.data?.error || (isLogin.value ? '登录失败' : '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  padding: 20px;
}

.auth-card {
  background: rgba(255, 255, 255, 0.70);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.60);
  border-radius: 16px;
  padding: 40px;
  width: 100%;
  max-width: 450px;
  box-shadow: var(--glass-shadow);
}

.auth-title {
  font-size: 32px;
  font-weight: bold;
  text-align: center;
  margin-bottom: 32px;
  color: var(--ink);
  letter-spacing: 1px;
  font-family: ui-serif, Georgia, 'Times New Roman', 'KaiTi', 'STKaiti', serif;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-soft);
}

.form-group input {
  padding: 12px 16px;
  border: 2px solid rgba(0, 0, 0, 0.10);
  border-radius: 8px;
  font-size: 15px;
  transition: border-color 0.3s;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
}

.form-group input:focus {
  outline: none;
  border-color: rgba(255, 214, 231, 1);
}

/* 验证码相关样式已移除 */

.error-message {
  padding: 12px;
  background: #fee;
  border: 1px solid #fcc;
  border-radius: 8px;
  color: #c33;
  font-size: 14px;
}

.success-message {
  padding: 12px;
  background: #efe;
  border: 1px solid #cfc;
  border-radius: 8px;
  color: #3c3;
  font-size: 14px;
}

.submit-btn {
  padding: 14px;
  background: linear-gradient(135deg, rgba(255, 214, 231, 1), rgba(217, 230, 255, 1));
  color: var(--ink);
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s;
  margin-top: 10px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.10);
}

.submit-btn:hover:not(:disabled) {
  filter: brightness(0.98);
}

.submit-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.auth-switch {
  margin-top: 24px;
  text-align: center;
  font-size: 14px;
  color: #666;
}

.auth-switch a {
  color: #667eea;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}

.auth-switch a:hover {
  text-decoration: underline;
}
</style>
