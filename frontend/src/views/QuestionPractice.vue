<template>
  <div class="practice-page">
    <header class="practice-top"><router-link to="/bookmarks">← 返回标记题目</router-link><span>MianMian · 专项重答</span><LogoutButton :disabled="submitting || voiceBusy" /></header>
    <main class="practice-main">
      <p v-if="loading && !context" class="notice" role="status">正在读取这道题的练习记录…</p>
      <div v-if="error" class="error" role="alert">{{ error }}<button class="secondary" :disabled="loading || submitting || voiceBusy" @click="load">刷新记录</button></div>
      <template v-if="context">
        <section class="practice-question"><span class="section-kicker">ONE QUESTION, ONE STEP FORWARD</span><div class="practice-label"><span class="pill green">{{ context.bookmark.job_track }}</span><span>已完成 {{ context.total }} 次重答</span></div><h1>{{ context.bookmark.question }}</h1><p>第一次与原面试回答比较，之后与最近一次重答比较。每次回答和对比结果都会保存。</p></section>
        <section v-if="result" class="practice-result" aria-labelledby="comparison-title">
          <div class="panel-head"><div><span class="section-kicker">YOUR PROGRESS</span><h2 id="comparison-title">第 {{ result.number }} 次重答对比</h2></div><span class="muted">对比基准：{{ result.previous.label }}</span></div>
          <p class="comparison-conclusion">{{ result.comparison.conclusion }}</p>
          <div class="comparison-grid">
            <article class="improved"><h3>这次哪里变好了</h3><ul v-if="result.comparison.improved.length"><li v-for="(text,i) in result.comparison.improved" :key="i">{{ text }}</li></ul><p v-else>本次还没有发现明确改善，可以先按下方建议再练一遍。</p></article>
            <article class="to-improve"><h3>还可以怎样进步</h3><ul v-if="result.comparison.needs_improvement.length"><li v-for="(text,i) in result.comparison.needs_improvement" :key="i">{{ text }}</li></ul><p v-else>本次未发现明显遗漏，可以尝试补充更具体的场景和约束。</p></article>
          </div>
          <section class="next-practice"><h3>下一次这样练</h3><ol><li v-for="(text,i) in result.comparison.next_practice" :key="i">{{ text }}</li></ol></section>
          <details class="answer-comparison"><summary>对照查看两次回答</summary><div class="comparison-grid"><article><h3>{{ result.previous.label }}</h3><p>{{ result.previous.answer }}</p></article><article><h3>第 {{ result.number }} 次重答</h3><p>{{ result.answer }}</p></article></div></details>
          <button class="primary another-attempt" @click="again">再练一次 →</button>
        </section>
        <section v-else class="practice-composer">
          <div class="panel-head"><h2>第 {{ context.total + 1 }} 次重答</h2><span class="muted">本次对比：{{ context.previous.label }}</span></div>
          <details class="previous-answer"><summary>回看{{ context.previous.label }}</summary><p>{{ context.previous.answer }}</p></details>
          <form @submit.prevent="submit">
            <label for="practice-answer">用自己的话重新回答</label>
            <textarea id="practice-answer" ref="answerInput" v-model="answer" :disabled="submitting || voiceBusy" placeholder="先给出结论，再展开思路、取舍和验证方式。" />
            <VoiceAnswerInput :key="route.params.id" :disabled="submitting || loading || context.in_progress" @busy="voiceBusy=$event" @transcript="appendTranscript" />
            <p v-if="answer.length > MAX_ANSWER_CHARACTERS" class="voice-limit" role="alert">全文已保留，回答超过 {{ MAX_ANSWER_CHARACTERS }} 字符，请精简后提交。</p>
            <div class="submit-row"><span :class="{overlimit: answer.length > MAX_ANSWER_CHARACTERS}">{{ answer.length }} / {{ MAX_ANSWER_CHARACTERS }} 字符</span><button class="primary" type="submit" :disabled="!canSubmit">{{ submitting ? '正在对比两次回答…' : '提交并查看进步' }}</button></div>
          </form>
          <p v-if="submitting" class="notice" role="status">正在分析本次相对上次的变化，请稍候…</p>
          <p v-else-if="context.in_progress" class="notice" role="status">这道题有一份回答正在评估，完成后会自动刷新。当前输入会保留。</p>
        </section>
        <section v-if="context.attempts.length" class="practice-history"><h2>重答记录</h2><p class="muted">最近 20 次 · 点击查看当次对比</p><button v-for="attempt in context.attempts" :key="attempt.id" class="attempt-row" :disabled="submitting || voiceBusy" @click="result=attempt"><span>第 {{ attempt.number }} 次重答<small>{{ formatDate(attempt.created_at) }} · 对比{{ attempt.previous.label }}</small></span><span>查看对比 →</span></button></section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { request } from '../api'
import { MAX_ANSWER_CHARACTERS } from '../interviewLimits'
import LogoutButton from '../components/LogoutButton.vue'
import VoiceAnswerInput from '../components/VoiceAnswerInput.vue'

const route=useRoute(),context=ref(null),answer=ref(''),result=ref(null),error=ref('')
const loading=ref(false),submitting=ref(false),answerInput=ref(null),voiceBusy=ref(false)
const canSubmit=computed(()=>context.value && !context.value.in_progress && !loading.value && !submitting.value && !voiceBusy.value && answer.value.trim() && answer.value.length<=MAX_ANSWER_CHARACTERS)
let controller,version=0,pollTimer,submission
const path=()=>`/api/v1/student/bookmarks/${encodeURIComponent(route.params.id)}/practice`
function formatDate(value){return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}
async function load() {
  clearTimeout(pollTimer); const current=version
  loading.value=true;error.value=''
  try {
    const data=await request(path(),{signal:controller.signal})
    if(current!==version)return
    context.value=data
    const saved=data.attempts.find(a=>a.id===submission?.request_id)
    if(saved)result.value=saved
    if(data.in_progress)pollTimer=setTimeout(load,4000)
  } catch(e){if(current===version && e.name!=='AbortError')error.value=e.message}
  finally {if(current===version)loading.value=false}
}
async function submit() {
  if(!canSubmit.value)return
  const current=version,baseline=context.value.previous.attempt_id,text=answer.value.trim()
  if(!submission || submission.answer!==text || submission.previous_attempt_id!==baseline) {
    submission={request_id:crypto.randomUUID(),previous_attempt_id:baseline,answer:text}
  }
  submitting.value=true;error.value=''
  try {
    const data=await request(path(),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(submission),signal:controller.signal})
    if(current!==version)return
    result.value=data
    context.value={...context.value, in_progress:false, total:Math.max(context.value.total,data.number),
      previous:{attempt_id:data.id,label:`第 ${data.number} 次重答`,answer:data.answer,feedback:data.comparison,created_at:data.created_at},
      attempts:[data,...context.value.attempts.filter(a=>a.id!==data.id)].slice(0,20)}
    await load()
  } catch(e){if(current===version && e.name!=='AbortError')error.value=`${e.message}。输入内容已保留，可重试。`}
  finally {if(current===version)submitting.value=false}
}
function appendTranscript(text) {
  answer.value += (answer.value ? '\n' : '') + text
}
async function again() {
  result.value=null;answer.value='';submission=null;error.value=''
  await nextTick();answerInput.value?.focus()
}
watch(()=>route.params.id,()=>{
  version++;controller?.abort();clearTimeout(pollTimer);controller=new AbortController()
  context.value=null;result.value=null;answer.value='';submission=null;submitting.value=false
  load()
},{immediate:true})
onBeforeUnmount(()=>{version++;controller?.abort();clearTimeout(pollTimer)})
</script>

<style scoped>
.practice-page { min-height: 100dvh; background: #f5f6f1; }
.practice-top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; padding: 18px clamp(20px,5vw,80px); background: #fff; border-bottom: 1px solid #e5e9df; }
.practice-top a { color: #49654e; text-decoration: none; font-size: 14px; }
.practice-top > span { color: #879181; font-size: 13px; }
.practice-main { max-width: 1180px; margin: auto; padding: clamp(24px,4vw,56px) clamp(16px,3vw,40px) 64px; }
.practice-question { margin-bottom: 28px; }
.practice-label { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin: 16px 0; color: #7c8876; font-size: 13px; }
.practice-question h1 { font-size: clamp(22px,2vw,30px); line-height: 1.7; }
.practice-question > p { color: #7e8976; font-size: 14px; line-height: 1.8; margin-top: 18px; }
.practice-composer,.practice-result,.practice-history { padding: clamp(20px,3vw,36px); background: white; border: 1px solid #e4e8dd; border-radius: 16px; margin-bottom: 24px; min-width: 0; }
.practice-main h2 { font-size: 20px; }
.practice-main h3 { font-size: 16px; line-height: 1.8; }
.previous-answer { margin: 22px 0; padding: 14px 16px; background: #f5f7f1; border-radius: 8px; }
.previous-answer p,.answer-comparison p { white-space: pre-wrap; line-height: 1.9; margin-top: 16px; font-size: 14px; }
form > label { font-size: 14px; color: #56664c; font-weight: 600; }
textarea { width: 100%; min-height: 280px; padding: 18px; border: 1px solid #ced9c4; border-radius: 10px; display: block; margin: 12px 0; resize: vertical; line-height: 1.9; font-size: 16px; color: #354a2c; background: #fcfdf9; }
.submit-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; font-size: 13px; color: #8a9482; }
.voice-limit { color: #ab3e2e; font-size: 13px; margin-bottom: 14px; line-height: 1.8; }
.submit-row .overlimit { color: #ab3e2e; }
.practice-main .primary { background: #386447; }
.comparison-conclusion { margin: 22px 0; line-height: 1.9; font-size: 16px; color: #43543b; white-space: pre-wrap; }
.comparison-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 18px; }
.comparison-grid > article,.next-practice { padding: 22px; border-radius: 12px; }
.improved { background: #eef6eb; color: #405c35; }
.to-improve { background: #fff6eb; color: #815b3d; }
.comparison-grid ul,.next-practice ol { padding-left: 20px; margin: 12px 0 0; }
.comparison-grid li,.next-practice li,.comparison-grid article > p { font-size: 14px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 10px; }
.next-practice { border: 1px solid #e6e9df; margin-top: 18px; }
.answer-comparison { margin: 24px 0; }
.answer-comparison article { background: #f7f8f4; }
.practice-history > .muted { margin: 8px 0 20px; }
.attempt-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; width: 100%; text-align: left; padding: 18px 0; border-top: 1px solid #e8ebdf; background: transparent; color: #456039; font-size: 14px; }
.attempt-row small { display: block; color: #8a9482; font-size: 12px; margin-top: 8px; overflow-wrap: anywhere; }
.attempt-row > span:last-child { flex-shrink: 0; font-size: 12px; }
.error button { margin: 10px 0 0 12px; }
@media(max-width:650px){ .practice-top > span { display: none; }.comparison-grid { grid-template-columns: minmax(0,1fr); }.comparison-grid > article,.next-practice { padding: 18px; } }
</style>
