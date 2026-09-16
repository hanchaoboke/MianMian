<template>
  <div class="bookmarks-page">
    <section class="review-intro">
      <div><span class="section-kicker">SAVE IT. SAY IT BETTER.</span><h2>把薄弱处，练成拿手题。</h2><p>回到当时的问题，理清知识点，再用自己的话回答一遍。</p></div>
      <div class="saved-count"><Bookmark :size="22" aria-hidden="true" /><strong>{{ total }}</strong><span>道已标记</span></div>
    </section>
    <div class="review-list-heading"><h3>我的复习清单</h3><span>最近标记优先 · 每页 10 题</span></div>
    <div v-if="error" class="error" role="alert">{{ error }} <button class="secondary" @click="loadPage(page)">重新加载</button></div>
    <p v-if="loading && !items.length" class="notice" role="status">正在读取标记题目…</p>
    <section v-else-if="!error && !items.length" class="review-empty">
      <Bookmark :size="32" aria-hidden="true" /><h3>给下一次进步，留个标记</h3><p>查看面试报告时，点击每道题右上角的「标记题目」。<br />题目、考查知识点和口语化标准回答会收录在这里。</p><router-link to="/" class="primary">去工作台查看面试报告</router-link>
    </section>
    <div class="review-cards" :aria-busy="loading">
      <article v-for="item in items" :key="item.id" class="review-card">
        <header class="review-card-header"><div class="review-meta"><span class="pill">{{ item.job_track || '面试复习' }}</span><span>{{ formatDate(item.interview_started_at) }} · 第 {{ item.turn }} 轮</span></div><button class="secondary remove-bookmark" :disabled="removing[item.id]" @click="remove(item)"><BookmarkCheck :size="16" aria-hidden="true" />{{ removing[item.id] ? '正在取消…' : '取消标记' }}</button></header>
        <h3 class="review-question">{{ item.question }}</h3>
        <router-link class="primary practice-link" :to="`/practice/${encodeURIComponent(item.id)}`">再次重答 · 看看进步 →</router-link>
        <p v-if="itemErrors[item.id]" class="error" role="alert">{{ itemErrors[item.id] }}</p>
        <template v-if="item.review">
          <section class="knowledge-section"><h4><ScanSearch :size="17" aria-hidden="true" />考查知识点</h4><ul><li v-for="(point,index) in item.review.knowledge_points" :key="index">{{ point }}</li></ul></section>
          <section class="spoken-section"><div class="spoken-heading"><h4><MessageCircle :size="17" aria-hidden="true" />口语化标准回答</h4><span>参考示范</span></div><p>{{ item.review.spoken_answer }}</p></section>
          <p class="practice-tip"><Lightbulb :size="16" aria-hidden="true" />先遮住答案试着说一遍，再对照补充。项目经历请替换成自己的真实情况。</p>
        </template>
        <div v-else-if="generating[item.id] || item.status==='generating'" class="review-generating" role="status"><span class="review-spinner" aria-hidden="true"></span><div><strong>正在整理这道题的复习内容</strong><p>题目已保存，知识点和口语化回答生成后会自动显示。</p></div></div>
        <div v-else class="review-pending"><p>{{ item.review_error || '题目已标记，正在准备整理知识点和口语化回答。' }}</p><button class="secondary" @click="generate(item)">{{ item.review_error ? '重新生成复习内容' : '生成复习内容' }}</button></div>
        <footer><span>标记于 {{ formatDate(item.created_at) }}</span><router-link :to="`/report/${encodeURIComponent(item.session_id)}`">查看原面试报告 <ArrowUpRight :size="15" aria-hidden="true" /></router-link></footer>
      </article>
    </div>
    <nav v-if="total>10" class="pagination" aria-label="标记题目分页"><button class="secondary" :disabled="page<=1 || loading" @click="loadPage(page-1)">上一页</button><span>第 {{ page }} / {{ pageCount }} 页 · 共 {{ total }} 题</span><button class="secondary" :disabled="page>=pageCount || loading" @click="loadPage(page+1)">下一页</button></nav>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ArrowUpRight, Bookmark, BookmarkCheck, Lightbulb, MessageCircle, ScanSearch } from 'lucide-vue-next'
import { request } from '../api'

const items=ref([]),total=ref(0),page=ref(1),loading=ref(false),error=ref('')
const generating=ref({}),removing=ref({}),itemErrors=ref({})
const pageCount=computed(()=>Math.max(1,Math.ceil(total.value/10)))
const attempted=new Set()
let active=true,version=0,pollTimer
function formatDate(value) {
  if(!value)return '未知时间'
  return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})
}
function schedule() {
  clearTimeout(pollTimer)
  if(!active)return
  // Generate at most one new answer at a time; other requests may originate in a report tab.
  const pending=items.value.find(item=>!item.review && item.status==='pending' && !item.review_error && !attempted.has(item.id))
  if(pending && !Object.values(generating.value).some(Boolean)) {void generate(pending);return}
  if(items.value.some(item=>item.status==='generating' && !generating.value[item.id])) {
    pollTimer=setTimeout(()=>loadPage(page.value,true),4000)
  }
}
async function loadPage(target=page.value,quiet=false) {
  clearTimeout(pollTimer)
  const current=++version
  if(!quiet)loading.value=true
  error.value=''
  try {
    const data=await request(`/api/v1/student/bookmarks?page=${target}`)
    if(!active || current!==version)return
    const lastPage=Math.max(1,Math.ceil(data.total/10))
    if(target>lastPage){await loadPage(lastPage,quiet);return}
    items.value=data.items;total.value=data.total;page.value=data.page
    schedule()
  } catch(e){if(active && current===version)error.value=e.message}
  finally {if(active && current===version)loading.value=false}
}
async function generate(item) {
  if(generating.value[item.id] || !active)return
  generating.value[item.id]=true;itemErrors.value[item.id]='';attempted.add(item.id)
  try {
    const data=await request(`/api/v1/student/bookmarks/${item.id}/review`,{method:'POST'})
    if(!active)return
    const current=items.value.find(row=>row.id===item.id)
    if(current)Object.assign(current,data)
  } catch(e) {
    if(!active)return
    itemErrors.value[item.id]=`题目仍保留在清单中：${e.message}`
    const current=items.value.find(row=>row.id===item.id)
    if(current){current.status='pending';current.review_error='复习内容暂未生成，请重试。'}
  } finally {generating.value[item.id]=false;schedule()}
}
async function remove(item) {
  if(removing.value[item.id])return
  removing.value[item.id]=true;itemErrors.value[item.id]=''
  try {
    await request(`/api/v1/student/bookmarks/${item.id}`,{method:'DELETE'})
    if(active)await loadPage(page.value)
  } catch(e){if(active)itemErrors.value[item.id]=e.message}
  finally {removing.value[item.id]=false}
}
onMounted(()=>loadPage())
onUnmounted(()=>{active=false;version++;clearTimeout(pollTimer)})
</script>

<style scoped>
.bookmarks-page { min-width: 0; }
.review-intro { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 24px; padding: clamp(24px,3vw,44px); border-radius: 18px; background: #253b36; color: #fff; }
.review-intro .section-kicker { color: #b7c5b6; }
.review-intro h2 { margin: 12px 0; }
.review-intro p { color: #c4d0c6; line-height: 1.8; font-size: 14px; }
.saved-count { display: flex; align-items: baseline; gap: 10px; padding: 18px 22px; border: 1px solid #ffffff24; background: #ffffff0a; border-radius: 12px; flex-shrink: 0; }
.saved-count svg { align-self: center; color: #efb388; }
.saved-count strong { font-size: 36px; font-weight: 500; }
.saved-count span { font-size: 13px; color: #c4d0c6; }
.review-list-heading { margin: 30px 0 18px; display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.review-list-heading h3 { font-size: 18px; }
.review-list-heading > span { color: #858b82; font-size: 12px; }
.review-cards { display: grid; gap: 24px; }
.review-card { min-width: 0; background: white; padding: var(--panel-padding); border: 1px solid var(--line); border-radius: 16px; }
.review-card-header, .review-meta, .spoken-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.review-meta { justify-content: flex-start; color: #858b82; font-size: 12px; min-width: 0; overflow-wrap: anywhere; }
.review-meta .pill { background: #f2f5ee; color: #657a57; }
.remove-bookmark { gap: 7px; font-size: 12px; }
.review-question { font-size: clamp(18px,1.5vw,24px); line-height: 1.8; margin: 20px 0 24px; max-width: 100ch; }
.practice-link { margin-bottom: 20px; }
.knowledge-section h4, .spoken-section h4 { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.knowledge-section h4 { color: #60734f; }
.knowledge-section ul { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 24px; padding: 0; list-style: none; }
.knowledge-section li { border: 1px solid #e6ebdf; background: #f7f9f3; padding: 8px 12px; border-radius: 8px; color: #58634c; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; max-width: 100%; }
.spoken-section { background: #fbf7f1; border: 1px solid #f0e6d8; border-radius: 12px; padding: clamp(18px,2vw,28px); }
.spoken-heading { color: #896142; }
.spoken-heading > span { color: #a18e78; font-size: 11px; }
.spoken-section p { margin-top: 18px; white-space: pre-wrap; font-size: clamp(14px,1.05vw,17px); line-height: 2; color: #4c4c43; max-width: 100ch; }
.practice-tip { display: flex; gap: 7px; color: #90887b; font-size: 12px; line-height: 1.9; margin-top: 14px; }
svg { flex-shrink: 0; }
.practice-tip svg { margin-top: 3px; }
.review-card footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; border-top: 1px solid var(--line); padding-top: 18px; margin-top: 24px; font-size: 12px; color: #8f958c; }
.review-card footer a { display: inline-flex; gap: 5px; align-items: center; color: #a66344; text-decoration: none; }
.review-generating, .review-pending { border: 1px dashed #d7dfce; background: #f7f9f3; border-radius: 12px; padding: 24px; color: #65765c; font-size: 14px; line-height: 1.8; }
.review-generating { display: flex; align-items: center; gap: 16px; }
.review-generating p { font-size: 13px; margin-top: 6px; }
.review-pending button { margin-top: 14px; }
.review-spinner { flex-shrink: 0; width: 22px; height: 22px; border: 2px solid #dbe4d2; border-top-color: #728966; border-radius: 50%; animation: review-spin 1s linear infinite; }
.review-empty { text-align: center; padding: clamp(32px,5vw,72px) 20px; background: #fff; border: 1px dashed #dcded4; border-radius: 16px; color: #6b7e5e; }
.review-empty h3 { margin: 20px 0 12px; }
.review-empty p { line-height: 2; font-size: 14px; color: #84897e; margin-bottom: 24px; }
@keyframes review-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .review-spinner { animation: none; } }
@media(max-width:650px) { .saved-count { padding: 12px 18px; }.saved-count strong { font-size: 28px; }.review-card-header { align-items: flex-start; }.review-meta { width: 100%; } }
</style>
