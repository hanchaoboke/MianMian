<template>
  <section class="interview-panel teacher-page">
    <div class="panel-head"><div><span class="section-kicker">CLASS MANAGEMENT</span><h2>班级与学生</h2></div><button class="secondary" :disabled="loading || busy" @click="load">刷新</button></div>
    <p class="description">在这里创建班级、查看成员和调整归属。新账号请到左侧“分配账号”创建。</p>
    <form class="create-class" @submit.prevent="createClass"><label class="field">新班级名称<input v-model.trim="newName" required maxlength="100" :disabled="busy" placeholder="例如：AI 应用开发 01 班" /></label><button class="primary" :disabled="busy || loading">创建班级</button></form>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <p v-if="loading" class="notice">正在加载班级和学生…</p>
    <template v-else>
      <p class="description">{{ classes.length }} 个班级 · {{ allStudents.length }} 名学生</p>
      <label class="field">查看班级<select v-model="selected"><option value="">全部班级</option><option v-for="c in classes" :key="c.name" :value="c.name">{{ c.name }}（{{ c.students.length }} 人）</option><option value="__unassigned__">未分班（{{ unassigned.length }} 人）</option></select></label>
      <p v-if="!classes.length && !unassigned.length" class="description">暂无班级，创建第一个班级开始管理。</p>
      <article v-for="group in visibleGroups" :key="group.name" class="library-item">
        <h3>{{ group.name }} <small>· {{ group.students.length }} 人</small></h3>
        <div v-if="group.name !== '未分班'" class="difficulty-settings"><strong>工作年限对应难度</strong><div class="difficulty-grid"><label v-for="option in experienceOptions" :key="option.value">{{ option.label }}<select v-model="group.difficulty_by_experience[option.value]" :disabled="busy"><option>EASY</option><option>MEDIUM</option><option>HARD</option></select></label></div><button class="secondary" :disabled="busy" @click="saveDifficulty(group)">保存难度设置</button></div>
        <p v-if="!group.students.length" class="description">暂无学生，可在“分配账号”中选择此班级，或从其他班级转入。</p>
        <div v-for="student in group.students" :key="student.user_id" class="student-row">
          <div><strong>{{ student.display_name || student.username }}</strong><small>{{ student.username }}</small></div>
          <label>调整班级<select :aria-label="`${student.display_name || student.username}的班级`" :value="student.class_name" :disabled="busy" @change="assign(student, $event)"><option value="">未分班</option><option v-for="c in classes" :key="c.name" :value="c.name">{{ c.name }}</option></select></label>
        </div>
      </article>
    </template>
  </section>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { request } from '../api'
const classes = ref([]), unassigned = ref([]), selected = ref(''), newName = ref(''), loading = ref(false), busy = ref(false), error = ref(''), notice = ref('')
const experienceOptions=[{value:'1',label:'1年'},{value:'1-3',label:'1～3年'},{value:'3-5',label:'3～5年'},{value:'5-7',label:'5～7年'},{value:'7+',label:'7年以上'}]
const allStudents = computed(() => [...unassigned.value, ...classes.value.flatMap(c => c.students)])
const visibleGroups = computed(() => [...classes.value, {name:'未分班', key:'__unassigned__', students:unassigned.value}].filter(c => (!selected.value && (c.name !== '未分班' || c.students.length)) || selected.value === (c.key || c.name)))
async function load() {
  loading.value = true; error.value = ''
  try {const data = await request('/api/v1/teacher/classes'); classes.value = data.items.map(group => ({...group, difficulty_by_experience: {...Object.fromEntries(experienceOptions.map(option => [option.value, option.value === '1' ? 'EASY' : option.value === '1-3' ? 'MEDIUM' : 'HARD'])), ...(group.difficulty_by_experience || {})}})); unassigned.value = data.unassigned}
  catch(e) {error.value = e.message} finally {loading.value = false}
}
async function createClass() {
  if(busy.value)return
  busy.value = true; error.value = ''; notice.value = ''
  try {await request('/api/v1/teacher/classes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newName.value})}); notice.value = `班级“${newName.value}”已创建`; selected.value = newName.value; newName.value = ''; await load()}
  catch(e) {error.value = e.message} finally {busy.value = false}
}
async function assign(student, event) {
  const name = event.target.value
  event.target.value = student.class_name
  busy.value = true; error.value = ''; notice.value = ''
  try {await request(`/api/v1/teacher/users/${student.user_id}/class`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({class_name:name})}); notice.value = `已更新 ${student.display_name || student.username} 的班级`; await load()}
  catch(e) {error.value = e.message} finally {busy.value = false}
}
async function saveDifficulty(group) {
  busy.value=true; error.value=''; notice.value=''
  try { await request(`/api/v1/teacher/classes/${encodeURIComponent(group.name)}/difficulty`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({difficulty_by_experience:group.difficulty_by_experience})}); notice.value=`已保存“${group.name}”的难度设置` }
  catch(e){error.value=e.message} finally{busy.value=false}
}
onMounted(load)
</script>
<style scoped>
.create-class { display: flex; align-items: end; gap: 14px; }
.create-class .field { flex: 1; margin: 14px 0 0; }
.create-class > .primary { flex-shrink: 0; }
.student-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 18px 0; border-bottom: 1px solid #eee; }
.student-row > div { min-width: 0; overflow-wrap: anywhere; }
.student-row small { display: block; color: #888; margin-top: 6px; }
.student-row label { font-size: 14px; color: #777; min-width: 0; flex: 0 1 260px; }
.student-row select { display: block; width: 100%; padding: 11px; border: 1px solid #ddd; border-radius: 7px; margin-top: 5px; }
.library-item h3 { line-height: 1.6; }
.library-item h3 small { font-size: 14px; color: #888; }
@media (max-width: 650px) {
  .student-row { align-items: start; flex-direction: column; gap: 10px; }
  .student-row label { flex: auto; width: 100%; }
  .student-row select { font-size: 16px; }
  .create-class { align-items: stretch; flex-direction: column; }
}
</style>
<style scoped>
.difficulty-settings{margin:18px 0;padding:16px;background:#faf9f4;border:1px solid #ece9df;border-radius:10px}.difficulty-settings strong{font-size:13px;color:#697466}.difficulty-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:12px 0}.difficulty-grid label{font-size:11px;color:#858b82}.difficulty-grid select{display:block;width:100%;margin-top:5px;padding:8px;border:1px solid #ddd;border-radius:6px;background:#fff;font-size:12px}@media(max-width:650px){.difficulty-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
