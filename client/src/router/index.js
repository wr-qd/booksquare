import { createRouter, createWebHistory } from 'vue-router'
import Auth from '../views/Auth.vue'
import Home from '../views/Home.vue'
import BookDetail from '../views/BookDetail.vue'
import BilibiliReviewDetail from '../views/BilibiliReviewDetail.vue'
import Bookshelf from '../views/Bookshelf.vue'
import Profile from '../views/Profile.vue'
import CreateCustomBook from '../views/CreateCustomBook.vue'
import ReaderSources from '../views/ReaderSources.vue'
import ReaderView from '../views/ReaderView.vue'

const routes = [
  {
    path: '/auth',
    name: 'Auth',
    component: Auth
  },
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/book/:id',
    name: 'BookDetail',
    component: BookDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/reader/sources/:bookId',
    name: 'ReaderSources',
    component: ReaderSources,
    meta: { requiresAuth: true }
  },
  {
    path: '/reader/view/:assetId',
    name: 'ReaderView',
    component: ReaderView,
    meta: { requiresAuth: true }
  },
  {
    path: '/book/:id/bilibili/:cvId',
    name: 'BilibiliReviewDetail',
    component: BilibiliReviewDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/bookshelf',
    name: 'Bookshelf',
    component: Bookshelf,
    meta: { requiresAuth: true }
  },
  {
    path: '/bookshelf/new',
    name: 'CreateCustomBook',
    component: CreateCustomBook,
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: Profile,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { left: 0, top: 0 }
  }
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !token) {
    // 需要登录但没有token，跳转到登录页
    next('/auth')
  } else if (to.path === '/auth' && token) {
    // 已登录但访问登录页，跳转到首页
    next('/')
  } else {
    next()
  }
})

export default router
