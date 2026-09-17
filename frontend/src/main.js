import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', component: () => import('./views/Workspace.vue') },
  { path: '/login', component: () => import('./views/Login.vue') },
  { path: '/teacher/login', component: () => import('./views/TeacherLogin.vue') },
  { path: '/interview/:id', component: () => import('./views/Interview.vue') },
  { path: '/teacher', component: () => import('./views/Teacher.vue') },
  { path: '/teacher/reports', component: () => import('./views/TeacherReports.vue') },
  { path: '/teacher/reports/:id', props: {teacher: true}, component: () => import('./views/Report.vue') },
  { path: '/teacher/accounts', component: () => import('./views/TeacherAccounts.vue') },
  { path: '/teacher/classes', component: () => import('./views/TeacherClasses.vue') },
  { path: '/teacher/evaluation', component: () => import('./views/TeacherEvaluation.vue') },
  { path: '/teacher/storage', meta: {adminOnly: true}, component: () => import('./views/AdminStorage.vue') },
  { path: '/teacher/staff-usage', props: { audience: 'staff' }, component: () => import('./views/TeacherUsage.vue') },
  { path: '/teacher/usage', component: () => import('./views/TeacherUsage.vue') },
  { path: '/report/:id', component: () => import('./views/Report.vue') },
  { path: '/bookmarks', component: () => import('./views/Bookmarks.vue') },
  { path: '/practice/:id', component: () => import('./views/QuestionPractice.vue') },
] })
router.beforeEach((to) => {
  const token = localStorage.getItem('mianmian-token')
  const user = JSON.parse(localStorage.getItem('mianmian-user') || 'null')
  const isTeacherPath = to.path === '/teacher' || to.path.startsWith('/teacher/')
  const isTeacherLogin = to.path === '/teacher/login'
  const isStudentLogin = to.path === '/login'
  if (isTeacherPath && !isTeacherLogin && !token) return '/teacher/login'
  if (isTeacherPath && !isTeacherLogin && token && !['ADMIN', 'TEACHER'].includes(user?.role)) return '/teacher/login'
  if (to.meta.adminOnly && user?.role !== 'ADMIN') return '/teacher'
  if (!isTeacherPath && !isStudentLogin && !token) return '/login'
  if (isTeacherLogin && token && ['ADMIN', 'TEACHER'].includes(user?.role)) return '/teacher'
  if (isStudentLogin && token && user?.role === 'STUDENT') return '/'
  return true
})
createApp(App).use(router).mount('#app')
