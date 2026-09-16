<template>
  <div class="report-page">
    <div class="report-head"><div><span class="section-kicker">POST-INTERVIEW REVIEW</span><h2>面试诊断</h2></div><button class="secondary" @click="$router.push('/')">← 回到工作台</button></div>
    <EvaluationSheetDownload v-if="report" :key="route.params.id" :session-id="String(route.params.id)" class="report-export" />
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-else-if="!report" class="report-loading">正在读取报告…</p>
    <template v-if="report"><div class="report-grid"><section class="score-card"><div class="score-ring"><strong>{{ report.overall_score }}</strong><span>/100</span></div><span class="pill green">{{ report.overall_score >= 80 ? '继续保持' : report.overall_score >= 60 ? '仍有提升空间' : '建议重点复习' }}</span><p>{{ report.summary }}</p></section><section class="dimensions"><span class="section-kicker">能力维度</span><div v-for="item in dimensions" :key="item.key" class="dimension"><div><span>{{ item.label }}</span><b>{{ report.dimensions[item.key] }}</b></div><div class="bar"><i :style="{width: `${report.dimensions[item.key]}%`}"/></div></div></section></div>
      <section class="recommendations interview-summary" aria-labelledby="interview-summary-title"><span class="section-kicker">INTERVIEW SUMMARY</span><h3 id="interview-summary-title">面试总结</h3>
        <p v-if="summaryLoading" class="notice" role="status">正在综合本场问答，整理你的优势与提升方向…</p>
        <div v-else-if="summaryError" class="error" role="alert">{{ summaryError }}<button class="secondary" @click="loadSummary">重新生成总结</button></div>
        <template v-else-if="summary"><p class="summary-conclusion">{{ summary.conclusion }}</p>
          <div class="summary-columns"><article class="summary-strengths"><h4>值得保持的优点</h4><ul v-if="summary.strengths.length"><li v-for="(item, index) in summary.strengths" :key="index">{{ item }}</li></ul><p v-else>本场回答中尚无足够证据归纳明确优势，可以先从下方重点建议着手练习。</p></article>
          <article class="summary-priorities"><h4>接下来重点提高</h4><ol><li v-for="(item, index) in summary.priorities" :key="index">{{ item }}</li></ol></article></div>
          <div class="summary-practice"><h4>下一步怎么练</h4><ol><li v-for="(item, index) in summary.next_steps" :key="index">{{ item }}</li></ol></div>
        </template>
      </section>
      <section class="recommendations"><span class="section-kicker">TURN BY TURN</span><h3>逐题复盘</h3>
        <p class="description">把想再练一次的题目标记下来，在「标记题目回顾」中查看知识点和口语化标准回答。</p>
        <article class="library-item" v-for="t in report.turns" :key="t.turn" :id="`turn-${t.turn}`">
          <div class="turn-toolbar"><span class="pill">第 {{ t.turn }} 轮 · {{ t.score }} 分</span>
            <button class="secondary bookmark-button" :class="{'is-marked': t.bookmark_id}" :aria-pressed="Boolean(t.bookmark_id)" :disabled="bookmarkState[t.turn]?.busy" @click="toggleBookmark(t)">
              <Bookmark :size="16" aria-hidden="true" /><span>{{ bookmarkState[t.turn]?.busy ? (bookmarkState[t.turn].removing ? '正在取消…' : t.bookmark_id ? '已标记 · 整理中…' : '正在保存…') : t.bookmark_id ? '已标记 · 取消标记' : '标记题目' }}</span>
            </button>
          </div>
          <p v-if="bookmarkState[t.turn]?.error" class="error" role="alert">{{ bookmarkState[t.turn].error }}</p>
          <p v-if="t.bookmark_id" class="bookmark-hint" role="status">{{ bookmarkState[t.turn]?.busy ? '题目已保存，正在整理复习内容，可稍后在回顾页查看。' : '已收录到你的复习清单。' }} <router-link to="/bookmarks">前往回顾 →</router-link></p>
          <h4>{{ t.question }}</h4><h5>你的回答</h5><p class="transcript">{{ t.answer }}</p><h5>面试反馈</h5><p class="transcript">{{ t.feedback }}</p>
        </article>
      </section>
    </template>
  </div>
</template>
<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Bookmark } from 'lucide-vue-next'
import { request } from '../api'
import EvaluationSheetDownload from '../components/EvaluationSheetDownload.vue'
const route=useRoute(),report=ref(null),error=ref('')
const summary=ref(null),summaryLoading=ref(false),summaryError=ref('')
const bookmarkState=ref({})
let controller, version=0
const dimensions=[{key:'engineering_depth',label:'AI 工程深度'},{key:'system_design',label:'系统设计'},{key:'star_structure',label:'STAR 表达'},{key:'stress_handling',label:'临场应变（内容评估）'}]
async function toggleBookmark(turn) {
  if(bookmarkState.value[turn.turn]?.busy)return
  const current=version, sessionId=route.params.id
  bookmarkState.value[turn.turn]={busy:true,error:'',removing:Boolean(turn.bookmark_id)}
  const state=bookmarkState.value[turn.turn]
  try {
    if(turn.bookmark_id) {
      await request(`/api/v1/student/bookmarks/${turn.bookmark_id}`,{method:'DELETE'})
      if(current===version)turn.bookmark_id=null
    } else {
      const item=await request('/api/v1/student/bookmarks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sessionId,turn:turn.turn})})
      if(current!==version)return
      turn.bookmark_id=item.id
      if(item.status==='pending') {
        try {await request(`/api/v1/student/bookmarks/${item.id}/review`,{method:'POST'})}
        catch(e){state.error=`题目已标记，复习内容暂未生成：${e.message}。可在回顾页重试。`}
      }
    }
  } catch(e) {state.error=e.message}
  finally {state.busy=false}
}
async function loadSummary() {
  if(summaryLoading.value)return
  const current=version, id=route.params.id
  summaryLoading.value=true;summaryError.value=''
  try {const data=await request(`/api/v1/interviews/${id}/summary`,{method:'POST',signal:controller.signal});if(current===version)summary.value=data}
  catch(e){if(current===version)summaryError.value=`总结暂未生成：${e.message}。逐题复盘仍可查看。`}
  finally{if(current===version)summaryLoading.value=false}
}
watch(()=>route.params.id, async id=>{
  controller?.abort();controller=new AbortController();const current=++version
  report.value=null;summary.value=null;error.value='';summaryError.value='';summaryLoading.value=false;bookmarkState.value={}
  try {const data=await request(`/api/v1/interviews/${id}/report`,{signal:controller.signal});if(current!==version)return;report.value=data;summary.value=data.interview_summary;if(!summary.value)await loadSummary()}
  catch(e){if(current===version)error.value=e.message}
},{immediate:true})
onUnmounted(()=>{version++;controller?.abort()})
</script>
<style scoped>
.report-export { margin:16px 0 24px; }
.summary-conclusion { font-size: clamp(15px, 1.1vw, 18px); line-height: 1.9; color: #42534a; white-space: pre-wrap; max-width: 100ch; }
.summary-columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: clamp(18px, 2vw, 30px); margin-top: 22px; }
.summary-columns article, .summary-practice { border-radius: 12px; padding: clamp(18px, 1.8vw, 30px); }
.summary-strengths { background: #f0f6f0; }
.summary-priorities { background: #fff6ec; }
.interview-summary h4 { font-size: 16px; margin-bottom: 12px; }
.interview-summary ul, .interview-summary ol { padding-left: 20px; margin: 0; }
.interview-summary li, .summary-strengths p { font-size: clamp(14px, 1vw, 16px); line-height: 1.9; margin: 10px 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.summary-practice { margin-top: 22px; border: 1px solid #e7e8e2; }
.summary-practice li { max-width: 100ch; }
.interview-summary .error button { display: block; margin-top: 10px; }
.turn-toolbar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.bookmark-button { gap: 7px; }
.bookmark-button svg { flex-shrink: 0; }
.bookmark-button.is-marked { color: #b5633f; border-color: #f0d1bd; background: #fff6ee; }
.bookmark-button.is-marked svg { fill: #f8d9c6; }
.bookmark-hint { font-size: 13px; color: #6d7e6b; margin-top: 14px; line-height: 1.8; }
.bookmark-hint a { color: #ab5d3b; white-space: nowrap; }
</style>
