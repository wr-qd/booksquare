import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

const bgUrl = import.meta.env.VITE_BG_IMAGE_URL
if (bgUrl) {
	document.documentElement.style.setProperty('--app-bg-image', `url("${bgUrl}")`)
}

const app = createApp(App)
app.use(router)
app.mount('#app')