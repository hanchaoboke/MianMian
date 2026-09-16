<template>
  <router-view v-if="isInterview || isLogin" />
  <div v-else class="app-shell">
    <aside class="sidebar" :class="{'student-sidebar': !isTeacher}">
      <div class="brand"><span class="brand-mark">M</span><div><strong>MianMian</strong><small>面面俱道 · AI 面试训练场</small></div></div>
      <template v-if="!isLogin">
        <nav v-if="isTeacher" aria-label="教师功能导航">
          <router-link to="/teacher" exact-active-class="active">▦ <span>题库管理</span></router-link>
          <router-link to="/teacher/classes" exact-active-class="active">▤ <span>班级管理</span></router-link>
          <router-link to="/teacher/accounts" exact-active-class="active">♙ <span>分配账号</span></router-link>
          <router-link to="/teacher/usage" exact-active-class="active">▥ <span>学生 Token 消耗</span></router-link>
          <router-link to="/teacher/staff-usage" exact-active-class="active">▥ <span>教师 Token 消耗</span></router-link>
        </nav>
        <nav v-else aria-label="学生功能导航"><router-link to="/" exact-active-class="active">⌁ <span>学员 · 面试工作台</span></router-link></nav>
        <button v-if="!isTeacher" class="calendar-toggle" :aria-expanded="calendarOpen" aria-controls="sidebar-calendar" @click="calendarOpen = !calendarOpen">面试日历 <span>{{ calendarOpen ? '收起 ↑' : '展开查看 ↓' }}</span></button>
        <div v-if="!isTeacher" id="sidebar-calendar" class="sidebar-calendar" :class="{'is-open':calendarOpen}"><InterviewCalendar /></div>
        <nav v-if="!isTeacher" class="bookmark-nav" aria-label="复习导航"><router-link to="/bookmarks" exact-active-class="active"><Bookmark :size="18" aria-hidden="true" /><span>标记题目回顾</span></router-link></nav>
        <div class="side-bottom"><div class="coach-card"><span class="status-dot"></span><div><b>AI 应用开发</b><small>简历驱动 · 专项练习</small></div></div></div>
      </template>
    </aside>
    <main class="app-main"><div class="page-container"><header class="page-header"><div><p class="eyebrow">MIANMIAN · 面面俱道</p><h1>{{ pageTitle }}</h1></div><LogoutButton /></header><router-view /></div></main>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import InterviewCalendar from './components/InterviewCalendar.vue'
import LogoutButton from './components/LogoutButton.vue'
import { Bookmark } from 'lucide-vue-next'
import { refreshHistory, clearHistory } from './studentHistory'
const route = useRoute()
const calendarOpen = ref(false)
watch(() => route.fullPath, () => { calendarOpen.value = false })
const isHome = computed(() => route.path === '/')
const isInterview = computed(() => route.path.startsWith('/interview/') || route.path.startsWith('/practice/'))
const isLogin = computed(() => ['/login', '/teacher/login'].includes(route.path))
const isTeacher = computed(() => route.path.startsWith('/teacher'))
watch(() => route.path, () => {
  if (isLogin.value || isTeacher.value || isInterview.value) clearHistory()
  else refreshHistory()
}, {immediate:true})
const pageTitle = computed(() => {
  if (isHome.value) {
    let user
    try { user = JSON.parse(localStorage.getItem('mianmian-user') || 'null') } catch {}
    const name = user?.display_name || user?.username
    return name ? `${name}，今天也来练一场` : '今天也来练一场'
  }
  return ({
  '/teacher': '题库管理',
  '/teacher/accounts': '分配账号',
  '/teacher/classes': '班级管理',
  '/teacher/usage': '学生 Token 消耗',
  '/teacher/staff-usage': '教师 Token 消耗',
  '/teacher/login': '教师登录',
  '/login': '学生训练入口',
  '/bookmarks': '标记题目回顾',
}[route.path] || '面试诊断')
})
</script>
