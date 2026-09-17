<template>
  <div class="report-page" :class="{'teacher-report': teacher}">
    <div class="report-head"><h2 v-if="teacher">{{ (report?.student?.display_name || report?.student?.username || '学生') + '的面试报告' }}</h2><router-link class="report-back" :to="teacher ? {path: '/teacher/reports', query: route.query} : '/'"><ArrowLeft :size="16" />{{ teacher ? '返回报告列表' : '回到工作台' }}</router-link><EvaluationSheetDownload v-if="report && !teacher" :key="route.params.id" :session-id="String(route.params.id)" class="report-export" /></div>
    <p v-if="teacher && report" class="report-student-meta">{{ report.student.class_name || '未分班' }} · {{ report.job_track }} · {{ new Date(report.started_at).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai', hour12: false}) }}</p>
    <BusinessScenarioBrief v-if="report?.interview_mode === 'BUSINESS_SCENARIO' && report.business_scenario" :scenario="report.business_scenario" />
    <p v-if="error" class="error" role="alert">{{ error }} <button class="secondary" @click="reload++">重试</button></p><p v-else-if="!report" class="report-loading">正在读取报告…</p>
    <template v-if="report"><div class="report-grid"><section class="score-card"><div class="score-ring"><strong>{{ report.overall_score }}</strong><span>/100</span></div><span class="pill green">{{ report.overall_score >= 80 ? '继续保持' : report.overall_score >= 60 ? '仍有提升空间' : '建议重点复习' }}</span><p>{{ report.summary }}</p></section><section class="dimensions"><span class="section-kicker">能力维度</span><div v-for="item in dimensions" :key="item.key" class="dimension"><div><span>{{ item.label }}</span><b>{{ report.dimensions[item.key] }}</b></div><div class="bar"><i :style="{width: `${report.dimensions[item.key]}%`}"/></div></div></section></div>
      <section class="recommendations interview-summary" aria-labelledby="interview-summary-title"><span class="section-kicker">INTERVIEW SUMMARY</span><h3 id="interview-summary-title">面试总结</h3>
        <p v-if="summaryLoading" class="notice" role="status">正在综合本场问答，整理优势与提升方向…</p>
        <div v-else-if="summaryError" class="error" role="alert">{{ summaryError }}<button class="secondary" @click="loadSummary">重新生成总结</button></div>
        <template v-else-if="summary"><p class="summary-conclusion">{{ summary.conclusion }}</p>
          <div class="summary-columns"><article class="summary-strengths"><h4>值得保持的优点</h4><ul v-if="summary.strengths.length"><li v-for="(item, index) in summary.strengths" :key="index">{{ item }}</li></ul><p v-else>本场回答中尚无足够证据归纳明确优势，可以先从下方重点建议着手练习。</p></article>
          <article class="summary-priorities"><h4>接下来重点提高</h4><ol><li v-for="(item, index) in summary.priorities" :key="index">{{ item }}</li></ol></article></div>
          <div class="summary-practice"><h4>下一步怎么练</h4><ol><li v-for="(item, index) in summary.next_steps" :key="index">{{ item }}</li></ol></div>
        </template>
      </section>
      <section class="recommendations turn-review" aria-labelledby="turn-review-heading"><div class="review-heading"><h3 id="turn-review-heading">逐题复盘</h3><span>{{ report.turns.length }} 道题</span></div>
        <nav v-if="report.turns.length > 1" class="turn-navigation" aria-label="跳转到面试题目"><button v-for="t in report.turns" :key="t.turn" @click="jumpToTurn(t.turn)"><span>第 {{ t.turn }} 题</span><small>{{ t.score }} 分</small></button></nav>
        <article class="library-item review-turn" v-for="t in report.turns" :key="t.turn" :id="`turn-${t.turn}`">
          <div class="turn-toolbar"><div class="turn-identity"><span class="turn-index">{{ String(t.turn).padStart(2,'0') }}</span><span class="turn-score">{{ t.score }}<small>/ 100</small></span></div>
            <button v-if="!teacher" class="secondary bookmark-button" :class="{'is-marked': t.bookmark_id}" :aria-pressed="Boolean(t.bookmark_id)" :disabled="bookmarkState[t.turn]?.busy" @click="toggleBookmark(t)">
              <Bookmark :size="16" aria-hidden="true" /><span>{{ bookmarkState[t.turn]?.busy ? (bookmarkState[t.turn].removing ? '正在取消…' : t.bookmark_id ? '已标记 · 整理中…' : '正在保存…') : t.bookmark_id ? '已标记 · 取消标记' : '标记题目' }}</span>
            </button>
          </div>
          <p v-if="bookmarkState[t.turn]?.error" class="error" role="alert">{{ bookmarkState[t.turn].error }}</p>
          <p v-if="!teacher && t.bookmark_id" class="bookmark-hint" role="status">{{ bookmarkState[t.turn]?.busy ? '题目已保存，正在整理复习内容，可稍后在回顾页查看。' : '已收录到你的复习清单。' }} <router-link to="/bookmarks">前往回顾 →</router-link></p>
          <h4 :id="`question-${t.turn}`" class="review-question" tabindex="-1">{{ t.question }}</h4>
          <TeacherQuestionCollect v-if="teacher" :key="`${route.params.id}-${t.turn}`" :session-id="String(route.params.id)" :turn="t" @saved="t.bank_question_id = $event.id; t.bank_trashed = !!$event.deleted_at" />
          <div class="turn-body"><section class="answer-pane" :aria-labelledby="`answer-title-${t.turn}`"><h5 :id="`answer-title-${t.turn}`"><MessageSquare :size="16" />{{ teacher ? '学生回答' : '你的回答' }}</h5><p class="transcript" :id="`answer-${t.turn}`">{{ t.answer.length > 360 && !expandedAnswers[t.turn] ? t.answer.slice(0,360) + '…' : t.answer }}</p><button v-if="t.answer.length > 360" class="answer-toggle" :aria-expanded="!!expandedAnswers[t.turn]" :aria-controls="`answer-${t.turn}`" @click="expandedAnswers[t.turn] = !expandedAnswers[t.turn]">{{ expandedAnswers[t.turn] ? '收起回答' : `展开完整回答 · ${t.answer.length} 字` }}<ChevronDown :size="15" :class="{'is-expanded':expandedAnswers[t.turn]}" /></button></section>
          <section class="feedback-pane" :aria-labelledby="`feedback-title-${t.turn}`"><h5 :id="`feedback-title-${t.turn}`"><NotebookPen :size="17" />面试反馈</h5><ReportFeedback :text="t.feedback" /></section></div>
        </article>
      </section>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Bookmark, ChevronDown, MessageSquare, NotebookPen } from 'lucide-vue-next'
import { request } from '../api'
import EvaluationSheetDownload from '../components/EvaluationSheetDownload.vue'
import TeacherQuestionCollect from '../components/TeacherQuestionCollect.vue'
import BusinessScenarioBrief from '../components/BusinessScenarioBrief.vue'
import ReportFeedback from '../components/ReportFeedback.vue'
const props = defineProps({teacher: {type: Boolean, default: false}})
const route=useRoute(),report=ref(null),error=ref(''),reload=ref(0)
const summary=ref(null),summaryLoading=ref(false),summaryError=ref('')
const bookmarkState=ref({})
const expandedAnswers=ref({})
function jumpToTurn(turn) {
  const target = document.getElementById(`question-${turn}`)
  document.getElementById(`turn-${turn}`)?.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block:'start'})
  target?.focus({preventScroll:true})
}
const reportBase = computed(() => props.teacher ? '/api/v1/teacher/interviews' : '/api/v1/interviews')
let controller, version=0
const dimensions=computed(()=>[{key:'engineering_depth',label:'AI 工程深度'},{key:'system_design',label:'系统设计'},{key:'star_structure',label:report.value?.interview_mode === 'BUSINESS_SCENARIO' ? '方案表达' : 'STAR 表达'},{key:'stress_handling',label:'临场应变（内容评估）'}])
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
  try {const data=await request(`${reportBase.value}/${id}/summary`,{method:'POST',signal:controller.signal});if(current===version)summary.value=data}
  catch(e){if(current===version)summaryError.value=`总结暂未生成：${e.message}。逐题复盘仍可查看。`}
  finally{if(current===version)summaryLoading.value=false}
}
watch(()=>[route.params.id, props.teacher, reload.value], async ([id])=>{
  controller?.abort();controller=new AbortController();const current=++version
  report.value=null;summary.value=null;error.value='';summaryError.value='';summaryLoading.value=false;bookmarkState.value={};expandedAnswers.value={}
  try {const data=await request(`${reportBase.value}/${id}/report`,{signal:controller.signal});if(current!==version)return;report.value=data;summary.value=data.interview_summary;if(!summary.value)await loadSummary()}
  catch(e){if(current===version)error.value=e.message}
},{immediate:true})
onUnmounted(()=>{version++;controller?.abort()})
</script>
<style scoped>
.report-page{container-type:inline-size}.report-back{display:inline-flex;align-items:center;gap:8px;color:#6b7e70;font-size:14px;min-height:40px;text-decoration:none}.report-back:hover{color:#2f6d4e}.report-head .report-export{margin:0 0 0 auto}.report-page .report-grid{margin-top:20px}.report-page .score-card,.report-page .dimensions{border-radius:10px}.report-page .interview-summary{border-radius:10px}.report-page .turn-review{padding:0;background:transparent;border:0;border-radius:0;margin-top:40px}.review-heading{display:flex;align-items:baseline;gap:12px;margin-bottom:18px}.review-heading h3{font-size:22px;margin:0}.review-heading>span{font-size:13px;color:#8a978e}.turn-navigation{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}.turn-navigation button{display:flex;align-items:center;gap:12px;border:1px solid #e1e7e1;border-radius:6px;padding:9px 13px;background:transparent;color:#506c59;font-size:13px;min-height:40px}.turn-navigation button:hover{background:#edf3ee;border-color:#bbd0bf}.turn-navigation small{font-size:11px;color:#88968b;font-variant-numeric:tabular-nums}.report-page .review-turn{padding:24px;margin:0 0 24px;background:#fff;border:1px solid #e1e7e2;border-radius:10px}.turn-identity{display:flex;align-items:center;gap:18px}.turn-index{font-size:20px;font-weight:500;color:#9aada0;font-variant-numeric:tabular-nums;letter-spacing:1px}.turn-score{display:flex;align-items:baseline;gap:4px;font-size:18px;color:#395e48;font-variant-numeric:tabular-nums}.turn-score small{font-size:11px;color:#8d9d91}.report-page .review-question{font-size:19px;line-height:1.8;font-weight:600;max-width:90ch;margin:20px 0 24px;scroll-margin-top:28px}.turn-body{display:grid;grid-template-columns:minmax(0,1fr);gap:24px;border-top:1px solid #e8ece7;padding-top:24px;margin-top:24px;align-items:start}.turn-body>section{min-width:0}.turn-body h5{display:flex;align-items:center;gap:8px;font-size:13px;color:#7d8f81;font-weight:500;line-height:1.6;margin:0 0 16px}.answer-pane .transcript{font-size:14px;line-height:1.95;color:#687b6d}.feedback-pane{border-left:2px solid #d5e4d8;padding-left:20px}.feedback-pane h5{color:#3c7251}.answer-toggle{display:flex;align-items:center;gap:6px;padding:10px 0;margin-top:6px;background:transparent;color:#538364;font-size:12px;min-height:40px}.answer-toggle .is-expanded{transform:rotate(180deg)}.report-page .bookmark-button{min-height:36px;padding:7px 11px;font-size:12px;border-radius:6px}.report-page .bookmark-hint{font-size:12px;margin-bottom:8px}.report-page .summary-conclusion{max-width:85ch}.report-page .interview-summary h3{font-size:22px}.report-page .summary-columns article{border-radius:6px}.report-page .summary-practice{border-radius:6px}
@container(min-width:880px){.turn-body{grid-template-columns:minmax(0,.9fr) minmax(0,1.25fr);gap:32px}.feedback-pane{padding-left:28px}}
@media(max-width:650px){.report-page .review-turn{padding:18px;margin-bottom:18px}.report-page .review-question{font-size:17px;margin:18px 0 20px}.turn-body{padding-top:20px;gap:26px}.feedback-pane{padding-left:14px}.report-head .report-export{margin-left:0}.report-page .turn-review{margin-top:30px}.turn-navigation{gap:6px}.turn-navigation button{padding:8px 10px;gap:8px}.turn-toolbar{gap:8px}.turn-identity{gap:12px}}
.report-student-meta{color:#718176;font-size:14px;line-height:1.8;margin-top:12px;overflow-wrap:anywhere}.teacher-report .recommendations{border:0;border-radius:0;background:transparent;padding:24px 0}.teacher-report .library-item{background:#fff;border-radius:8px}.teacher-report .summary-columns article,.teacher-report .summary-practice{border-radius:8px}.teacher-report h2{font-size:24px;overflow-wrap:anywhere}.teacher-report .summary-conclusion,.teacher-report .transcript{font-size:15px}.teacher-report .library-item h4{font-size:18px}
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
