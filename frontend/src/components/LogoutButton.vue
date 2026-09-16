<template><button class="logout-button" :disabled="busy || disabled" @click="logout">{{ busy ? '正在退出…' : '退出登录' }}</button></template>
<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { request } from '../api'
import { clearHistory } from '../studentHistory'
defineProps({disabled:Boolean})
const router = useRouter(), route = useRoute(), busy = ref(false)
async function logout() {
  if (busy.value) return
  busy.value = true
  const destination = route.path.startsWith('/teacher') ? '/teacher/login' : '/login'
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 5000)
  try { await request('/api/v1/auth/logout', {method:'POST', signal:controller.signal}) }
  catch { /* Clear this browser's login even when the server is unreachable. */ }
  finally {
    clearTimeout(timeout)
    localStorage.removeItem('mianmian-token'); localStorage.removeItem('mianmian-user')
    clearHistory()
    await router.replace(destination)
    busy.value = false
  }
}
</script>
<style scoped>
.logout-button{flex-shrink:0;border:1px solid #e1dcd3;background:#fff;color:#796555;border-radius:8px;padding:10px 14px;font-size:12px;white-space:nowrap}.logout-button:hover{background:#fff2e9}.logout-button:focus-visible{outline:2px solid #c7754f;outline-offset:3px}
</style>
