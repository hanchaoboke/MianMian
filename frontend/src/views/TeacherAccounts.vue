<template>
  <section class="interview-panel teacher-page">
    <span class="section-kicker">ACCOUNT MANAGEMENT</span>
    <h2>创建学生账号</h2>
    <p class="description">由管理员分配用户名、初始密码和班级。</p>
    <form @submit.prevent="createAccount">
      <div class="field-grid">
        <label class="field">用户名<input v-model.trim="account.username" required minlength="2" maxlength="50" autocomplete="off" :disabled="busy" /></label>
        <label class="field">初始密码<input v-model="account.password" type="password" required minlength="6" maxlength="128" autocomplete="new-password" :disabled="busy" /></label>
        <label class="field">姓名<input v-model.trim="account.display_name" maxlength="80" :disabled="busy" placeholder="用于首页称呼和学生账单" /></label>
        <label v-if="account.role === 'STUDENT'" class="field">分配班级<select v-model="account.class_name" :disabled="busy"><option value="">暂不分班</option><option v-for="c in classes" :key="c.name" :value="c.name">{{ c.name }}</option></select><small>班级请在左侧“班级管理”中提前创建。</small></label>
        <label v-if="isAdmin" class="field">账号角色<select v-model="account.role" :disabled="busy"><option value="STUDENT">学生</option><option value="TEACHER">教师</option></select></label>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>
      <button class="primary" :disabled="busy" type="submit">{{ busy ? '正在创建…' : '创建账号' }}</button>
    </form>
  </section>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { request } from '../api'
const classes = ref([])
const isAdmin = JSON.parse(localStorage.getItem('mianmian-user') || 'null')?.role === 'ADMIN'
const initialAccount = () => ({ username: '', password: '', display_name: '', class_name: '', role: 'STUDENT' })
const account = ref(initialAccount()), busy = ref(false), error = ref(''), notice = ref('')
onMounted(async () => {try {classes.value = (await request('/api/v1/teacher/classes')).items} catch(e) {error.value = e.message}})
async function createAccount() {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const result = await request('/api/v1/teacher/users', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(account.value),
    })
    notice.value = `已创建${result.role === 'TEACHER' ? '教师' : '学生'}账号 ${result.username}`
    account.value = initialAccount()
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
