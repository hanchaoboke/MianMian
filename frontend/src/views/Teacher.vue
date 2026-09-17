<template>
  <section class="teacher-page">
    <details class="library-import">
    <summary><span><Upload :size="18" />导入面试资料</span><Plus :size="18" /></summary>
    <div class="library-import-body">
    <span class="section-kicker">QUESTION LIBRARY</span><h2>导入你的面试资料</h2>
    <p class="description">支持 Markdown、PDF、DOCX，单个文件不超过 10 MB。纯题目和带答案的题目都可导入；先预览校对，再保存到题库。</p>
    <label class="field">适用岗位<input v-model.trim="jobTrack" maxlength="100" :disabled="busy || !!draft" list="job-tracks" /><small>本次导入的题目将归入此岗位，学生可按岗位选择题库。</small></label><datalist id="job-tracks"><option v-for="track in tracks" :key="track" :value="track" /></datalist>
    <label class="upload-zone">{{ importing ? '正在导入题目，请稍候…' : '选择题库文档' }}
      <input type="file" accept=".md,.markdown,.pdf,.docx" :disabled="busy || !!draft" @change="importFile" />
      <small>扫描 PDF 请先进行 OCR。资料文本将发送给 DeepSeek 进行整理。</small>
    </label>
    <div v-if="importStatus" class="operation-status" role="status" aria-live="polite">
      <strong>{{ importStatus }}</strong>
      <progress aria-label="题库导入进度" :value="importPercent ?? undefined" max="100" />
      <small v-if="importProgress.total">已处理 {{ importProgress.completed }} / {{ importProgress.total }} 个单元，识别 {{ importProgress.questions }} 道题</small>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <section v-if="draft" class="draft-section">
      <div class="commit-toolbar">
        <button class="primary" :disabled="busy || !validDraft" @click="commit">{{ saving ? '正在入库…' : `确认 ${draft.questions.length} 道题入库` }}</button>
        <p v-if="!validDraft" class="error">请补齐题目与原文出处后再入库，至少保留一道题。</p>
        <p v-if="commitError" class="error" role="alert">{{ commitError }}</p>
        <p v-if="draftDuplicateCount" class="notice" role="status">检测到 {{ draftDuplicateCount }} 道题目内容重复，入库时会自动跳过重复项。</p>
        <div v-if="saving" class="operation-status" role="status"><strong>正在提交并写入题库，请稍候…</strong><progress aria-label="题库入库进度" /></div>
      </div>
      <div class="panel-head"><h3>{{ draft.filename }} · {{ draft.questions.length }} 道待校对</h3><button class="secondary" :disabled="busy" @click="discard">放弃本次导入</button></div>
      <details><summary>查看提取原文</summary><pre class="source-text">{{ draft.source_text }}</pre></details>
      <article v-for="(q, index) in draft.questions" :key="index" class="question-editor">
        <div class="panel-head"><b>题目 {{ index + 1 }}</b><button class="secondary" :disabled="busy" @click="draft.questions.splice(index, 1)">移除</button></div>
        <label class="field">题目<textarea v-model="q.question" maxlength="4000" :disabled="busy" /></label>
        <div class="field-grid"><label class="field">分类<input v-model="q.category" maxlength="100" :disabled="busy" /></label><label class="field">难度<select v-model="q.difficulty" :disabled="busy"><option>EASY</option><option>MEDIUM</option><option>HARD</option></select></label></div>
        <label class="field">参考答案 <small>{{ q.answer ? '来自原文，可人工修订' : '原文未提供，可留空' }}</small><textarea v-model="q.answer" maxlength="12000" placeholder="原文未提供答案" :disabled="busy" /></label>
        <details><summary>题目原文出处</summary><pre class="source-text">{{ q.source_quote }}</pre></details>
      </article>
      <button class="primary" :disabled="busy || !validDraft" @click="commit">{{ saving ? '正在入库…' : '确认保存到题库' }}</button>
      <p v-if="commitError" class="error" role="alert">{{ commitError }}</p>
      <progress v-if="saving" aria-label="保存进度" />
    </section>
    <div v-if="savedCount !== null" ref="savedStatus" class="operation-status" role="status"><strong>入库完成 · {{ savedCount }} 道题</strong><progress aria-label="题库入库进度" :value="100" max="100" /></div>
    </div></details>
    <section ref="librarySection" class="library-section">
      <div class="library-heading"><div><span class="section-kicker">QUESTION LIBRARY</span><h2>{{ libraryState === 'trash' ? '题目回收箱' : '面试题库' }}</h2></div><div class="library-tabs" role="group" aria-label="题库状态"><button :aria-pressed="libraryState === 'active'" :disabled="libraryLoading || !!actionBusy" @click="switchState('active')"><Library :size="16" />在用题目 <span>{{ counts.active }}</span></button><button :aria-pressed="libraryState === 'trash'" :disabled="libraryLoading || !!actionBusy" @click="switchState('trash')"><Trash2 :size="16" />回收箱 <span>{{ counts.trash }}</span></button></div></div>
      <p v-if="actionNotice" class="library-action-notice" role="status">{{ actionNotice }}<button v-if="undoId" class="secondary" :disabled="!!actionBusy" @click="manageQuestion({id: undoId}, 'restore')"><Undo2 :size="15" />撤销</button></p>
      <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>
      <label class="field">按适用岗位查看<select v-model="filterTrack" :disabled="libraryLoading" @change="changePage(1)"><option value="">全部岗位</option><option v-for="track in tracks" :key="track" :value="track">{{ track }}</option></select></label>
      <div v-if="totalQuestions" class="library-pagination" aria-label="题库分页">
        <span>共 {{ totalQuestions }} 道题<span v-if="totalPages > 1"> · 第 {{ page }} / {{ totalPages }} 页</span></span>
        <template v-if="totalPages > 1"><button class="secondary" title="上一页" aria-label="上一页题目" :disabled="page <= 1 || libraryLoading" @click="changePage(page - 1)"><ChevronLeft :size="16" /></button>
        <label><select :value="page" :disabled="libraryLoading" aria-label="题库页码" @change="changePage(Number($event.target.value))"><option v-for="n in totalPages" :key="n" :value="n">第 {{ n }} 页</option></select></label>
        <button class="secondary" title="下一页" aria-label="下一页题目" :disabled="page >= totalPages || libraryLoading" @click="changePage(page + 1)"><ChevronRight :size="16" /></button></template>
      </div>
      <p v-if="libraryLoading" class="notice" role="status">正在加载题目…</p>
      <p v-if="libraryError" class="error" role="alert">{{ libraryError }} <button class="secondary" @click="changePage(page)">重试</button></p>
      <div v-if="!totalQuestions && !libraryLoading && !libraryError" class="library-empty"><Trash2 v-if="libraryState === 'trash'" :size="30" /><Library v-else :size="30" /><h3>{{ libraryState === 'trash' ? '回收箱是空的' : filterTrack ? '该岗位暂无题目' : '题库暂无题目' }}</h3><router-link v-if="libraryState === 'active'" to="/teacher/reports">前往学生面试报告选题 <ArrowUpRight :size="15" /></router-link></div>
      <article v-for="q in questions" :key="q.id" class="library-item">
        <span class="pill">{{ q.category }} · {{ q.difficulty }}</span><h4>{{ q.question }}</h4><p class="description">{{ q.job_track }} · {{ q.source_file }}</p>
        <form v-if="libraryState === 'active' && answerEdits[q.id] !== undefined" @submit.prevent="saveAnswer(q)">
          <label class="field">适用岗位<input v-model.trim="trackEdits[q.id]" required maxlength="100" list="job-tracks" :disabled="answerSaving[q.id]" /></label>
          <label class="field">参考答案<textarea v-model="answerEdits[q.id]" maxlength="12000" :disabled="answerSaving[q.id]" placeholder="填写或修改参考答案，可留空" /></label>
          <small>{{ answerEdits[q.id].length }} / 12000</small>
          <button class="secondary ai-answer-button" type="button" :disabled="answerSaving[q.id] || answerSuggesting[q.id]" @click="suggestAnswer(q)">{{ answerSuggesting[q.id] ? '正在生成参考答案…' : '让大模型生成参考答案' }}</button>
          <small class="field-help">生成后会填入编辑框，你可以修改后再保存；调用会计入当前教师 Token 账单。</small>
          <div class="answer-edit-actions"><button class="primary" type="submit" :disabled="answerSaving[q.id]">{{ answerSaving[q.id] ? '正在保存…' : '保存答案' }}</button><button class="secondary" type="button" :disabled="answerSaving[q.id]" @click="cancelAnswer(q.id)">取消</button></div>
        </form>
        <template v-else>
          <details v-if="q.answer"><summary>参考答案</summary><pre class="source-text">{{ q.answer }}</pre></details><small v-else>未提供参考答案</small>
          <div class="library-item-actions"><button v-if="libraryState === 'active'" class="secondary" :disabled="!!actionBusy" @click="editAnswer(q)"><Pencil :size="15" />编辑答案与岗位</button><button v-if="libraryState === 'active'" class="library-icon" title="移入回收箱" aria-label="移入回收箱" :disabled="!!actionBusy" @click="manageQuestion(q, 'trash')"><Archive :size="18" /></button><template v-else><span class="trash-date">{{ new Date(q.deleted_at).toLocaleDateString('zh-CN', {timeZone: 'Asia/Shanghai'}) }} 移入</span><button class="secondary" :disabled="!!actionBusy" @click="manageQuestion(q, 'restore')"><Undo2 :size="15" />恢复题目</button><button class="library-icon danger" title="永久删除" aria-label="永久删除" :disabled="!!actionBusy" @click="deleteTarget = q.id"><Trash2 :size="18" /></button></template></div>
          <div v-if="deleteTarget === q.id" class="library-delete-confirm" role="alert"><strong>永久删除这道题？</strong><p>删除后无法恢复，已有面试报告仍会保留。</p><div><button class="secondary" :disabled="!!actionBusy" @click="deleteTarget = ''">取消</button><button class="secondary danger" :disabled="!!actionBusy" @click="manageQuestion(q, 'delete')"><Trash2 :size="15" />{{ actionBusy ? '正在删除…' : '确认永久删除' }}</button></div></div>
        </template>
        <p v-if="answerErrors[q.id]" class="error" role="alert">{{ answerErrors[q.id] }}</p>
        <p v-if="answerNotices[q.id]" class="notice" role="status">{{ answerNotices[q.id] }}</p>
      </article>
      <div v-if="totalPages > 1" class="library-pagination"><span>第 {{ page }} / {{ totalPages }} 页</span><button class="secondary" :disabled="page <= 1 || libraryLoading" @click="changePage(page - 1)">上一页</button><button class="secondary" :disabled="page >= totalPages || libraryLoading" @click="changePage(page + 1)">下一页</button></div>
    </section>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Archive, ArrowUpRight, ChevronLeft, ChevronRight, Library, Pencil, Plus, Trash2, Undo2, Upload } from 'lucide-vue-next'
import { request, importQuestions } from '../api'
const importing = ref(false), saving = ref(false), busy = computed(() => importing.value || saving.value)
const importStatus = ref(''), importPercent = ref(null), importProgress = ref({}), commitError = ref(''), savedCount = ref(null)
const savedStatus = ref(null)
let importController, libraryVersion = 0
const jobTrack = ref('AI 应用开发工程师'), error = ref(''), notice = ref(''), draft = ref(null), questions = ref([])
const page = ref(1), totalQuestions = ref(0), libraryLoading = ref(false), libraryError = ref(''), librarySection = ref(null)
const totalPages = computed(() => Math.max(1, Math.ceil(totalQuestions.value / 10)))
const answerEdits = ref({}), answerSaving = ref({}), answerErrors = ref({}), answerNotices = ref({})
const answerSuggesting = ref({})
const trackEdits = ref({}), tracks = ref([]), filterTrack = ref('')
const route = useRoute(), router = useRouter()
const libraryState = ref(route.query.state === 'trash' ? 'trash' : 'active'), counts = ref({active: 0, trash: 0})
const actionBusy = ref(''), actionError = ref(''), actionNotice = ref(''), undoId = ref(''), deleteTarget = ref('')
async function switchState(state) {
  if (libraryLoading.value || actionBusy.value) return
  libraryState.value = state; filterTrack.value = ''; deleteTarget.value = ''; actionError.value = ''
  questions.value = []; totalQuestions.value = 0
  await router.replace({query: state === 'trash' ? {state: 'trash'} : {}})
  await changePage(1)
}
async function manageQuestion(q, action) {
  if (actionBusy.value) return
  actionBusy.value = q.id; actionError.value = ''; actionNotice.value = ''; undoId.value = ''
  try {
    await request(`/api/v1/teacher/question-bank/${q.id}${action === 'delete' ? '' : `/${action}`}`, {method: action === 'delete' ? 'DELETE' : 'POST'})
    deleteTarget.value = ''; cancelAnswer(q.id)
    actionNotice.value = action === 'trash' ? '题目已移入回收箱' : action === 'restore' ? '题目已恢复到题库' : '题目已永久删除'
    if (action === 'trash') undoId.value = q.id
    try { await load() } catch { actionError.value = '操作已完成，列表刷新失败，请重试加载。' }
  } catch(e) { actionError.value = e.message }
  finally { actionBusy.value = '' }
}
const validDraft = computed(() => draft.value?.questions.length && draft.value.questions.every(q => q.question.trim() && q.source_quote.trim()))
const draftDuplicateCount = computed(() => {
  if (!draft.value) return 0
  const seen = new Set(); let duplicates = 0
  for (const q of draft.value.questions) { const key = (q.question || '').replace(/\s+/g, '').trim().toLocaleLowerCase(); if (key && seen.has(key)) duplicates++; seen.add(key) }
  return duplicates
})
async function load(targetPage = page.value) {
  const current = ++libraryVersion
  libraryLoading.value = true; libraryError.value = ''
  try {
    const data = await request(`/api/v1/teacher/question-bank?page=${targetPage}&state=${libraryState.value}${filterTrack.value ? `&job_track=${encodeURIComponent(filterTrack.value)}` : ''}`)
    if (current !== libraryVersion) return
    counts.value = data.counts || {active: data.total, trash: 0}
    const lastPage = Math.max(1, Math.ceil(data.total / 10))
    if (targetPage > lastPage) return await load(lastPage)
    tracks.value = data.tracks
    questions.value = data.items; totalQuestions.value = data.total; page.value = data.page
  } catch (e) { if (current === libraryVersion) libraryError.value = e.message; throw e } finally { if (current === libraryVersion) libraryLoading.value = false }
}
async function changePage(targetPage) {
  if (libraryLoading.value) return
  try { await load(targetPage); await nextTick(); librarySection.value?.scrollIntoView({behavior: 'smooth', block: 'start'}) } catch {}
}
function editAnswer(q) { answerEdits.value[q.id] = q.answer || ''; trackEdits.value[q.id] = q.job_track || '通用岗位'; answerErrors.value[q.id] = ''; answerNotices.value[q.id] = '' }
function cancelAnswer(id) { delete answerEdits.value[id]; delete answerErrors.value[id] }
async function saveAnswer(q) {
  if (answerSaving.value[q.id]) return
  answerSaving.value[q.id] = true; answerErrors.value[q.id] = ''
  try {
    const updated = await request(`/api/v1/teacher/question-bank/${q.id}/answer`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({answer: answerEdits.value[q.id], job_track: trackEdits.value[q.id]})})
    const index = questions.value.findIndex(item => item.id === q.id)
    if (index >= 0) questions.value[index] = updated
    delete answerEdits.value[q.id]; answerNotices.value[q.id] = '答案与适用岗位已保存'
    await load(1)
  } catch (e) { answerErrors.value[q.id] = `保存失败：${e.message}。修改内容已保留，可重试。` } finally { answerSaving.value[q.id] = false }
}
async function suggestAnswer(q) {
  if (answerSuggesting.value[q.id]) return
  answerSuggesting.value[q.id] = true; answerErrors.value[q.id] = ''
  try { const result = await request(`/api/v1/teacher/question-bank/${q.id}/suggest-answer`, {method:'POST'}); answerEdits.value[q.id] = result.answer; answerNotices.value[q.id] = '参考答案已生成，请校对后保存' }
  catch (e) { answerErrors.value[q.id] = `生成失败：${e.message}。原有内容已保留，可重试。` }
  finally { answerSuggesting.value[q.id] = false }
}
async function importFile(e) {
  const file = e.target.files?.[0]; e.target.value = ''; if (!file) return
  if (file.size > 10 * 1024 * 1024) { error.value = '文件不得超过 10 MB'; return }
  if (busy.value) return
  importing.value = true; error.value = ''; notice.value = ''; savedCount.value = null; commitError.value = ''
  importPercent.value = null; importProgress.value = {}; importStatus.value = '正在上传并解析文档…'
  importController = new AbortController()
  try {
    const body = new FormData(); body.append('file', file); body.append('job_track', jobTrack.value)
    draft.value = await importQuestions(body, (event) => {
      importProgress.value = event
      importPercent.value = event.total ? Math.round(event.completed / event.total * 95) : null
      importStatus.value = event.total && event.completed === event.total ? '抽取完成，正在保存预览结果…' : '正在识别题目与参考答案…'
    }, importController.signal)
    importPercent.value = 100; importStatus.value = `导入完成，共 ${draft.value.questions.length} 道题，请校对后入库`
  } catch (e) { error.value = e.name === 'AbortError' ? '导入已取消' : e.message; importStatus.value = '导入未完成，请重试'; importPercent.value = 0 } finally { importing.value = false }
}
function discard() { draft.value = null; notice.value = ''; commitError.value = ''; importStatus.value = '' }
async function commit() {
  if (busy.value || !validDraft.value) return
  saving.value = true; error.value = ''; commitError.value = ''; notice.value = ''; savedCount.value = null
  try {
    const result = await request(`/api/v1/teacher/question-bank/import/${draft.value.import_id}/commit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ questions: draft.value.questions }) })
    savedCount.value = result.question_ids.length
    const skipped = result.skipped_duplicates || 0
    notice.value = skipped ? `已保存 ${savedCount.value} 道题目，跳过 ${skipped} 道重复题目。学员可在训练设置中选择。` : `已保存 ${savedCount.value} 道题目，学员可在训练设置中选择。`; draft.value = null; importStatus.value = ''
    try { libraryState.value = 'active'; filterTrack.value = ''; await router.replace({query: {}}); await load(1) } catch (e) { error.value = `入库已成功，但列表刷新失败：${e.message}` }
    await nextTick(); savedStatus.value?.scrollIntoView({behavior: 'smooth', block: 'center'})
  } catch (e) { commitError.value = e.message; error.value = `入库失败：${e.message}。校对内容已保留，可重试。` } finally { saving.value = false }
}
onUnmounted(() => { libraryVersion++; importController?.abort() })
watch(() => route.query.state, value => {
  const state = value === 'trash' ? 'trash' : 'active'
  if (state === libraryState.value) return
  libraryState.value = state; filterTrack.value = ''; questions.value = []; totalQuestions.value = 0; deleteTarget.value = ''
  load(1).catch(() => {})
})
onMounted(async () => { try { await load() } catch (e) { error.value = e.message } })
</script>
<style scoped>
.library-import{border-bottom:1px solid #dbe4de;margin-bottom:32px;padding-bottom:20px}.library-import>summary{display:flex;justify-content:space-between;align-items:center;gap:16px;list-style:none;color:#426550;font-size:14px;cursor:pointer;min-height:36px}.library-import>summary::-webkit-details-marker{display:none}.library-import>summary>span{display:flex;align-items:center;gap:9px}.library-import[open]>summary>svg{transform:rotate(45deg)}.library-import-body{padding-top:24px}.library-import-body>h2{font-size:22px}.library-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap}.library-heading h2{font-size:24px;margin-top:8px}.library-tabs{display:flex;gap:4px;padding:4px;background:#edf1ee;border-radius:6px;max-width:100%}.library-tabs button{display:flex;align-items:center;justify-content:center;gap:7px;min-height:40px;border:0;border-radius:4px;background:transparent;color:#78887c;padding:8px 14px;font-size:13px;cursor:pointer}.library-tabs button[aria-pressed=true]{background:#fff;color:#285b40;box-shadow:0 1px 4px #193b2310}.library-tabs span{font-size:12px;font-variant-numeric:tabular-nums}.library-section>.field{max-width:340px;margin-top:24px}.library-item{background:#fff;border-radius:8px}.library-item h4{font-size:18px}.library-item .description{font-size:13px}.library-item-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:20px}.library-item-actions button{gap:6px}.library-icon{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;flex-shrink:0;border:1px solid #dde5df;background:transparent;border-radius:6px;color:#829086;cursor:pointer}.library-icon:hover{background:#f2f5f3;color:#395947}.library-icon:disabled{opacity:.5;cursor:wait}.library-icon:last-child{margin-left:auto}.danger{color:#ac4d48;border-color:#e9c9c4}.trash-date{font-size:12px;color:#849086;margin-right:auto}.library-delete-confirm{padding:18px 0 0;border-top:1px solid #e8d4d0;margin-top:18px;color:#9e4b46;font-size:14px}.library-delete-confirm p{font-size:13px;margin:8px 0 14px}.library-delete-confirm>div{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}.library-action-notice{display:flex;align-items:center;gap:16px;margin:20px 0;padding:12px 16px;background:#eaf3ed;color:#397353;font-size:14px;flex-wrap:wrap;border-radius:6px}.library-empty{text-align:center;color:#85948b;padding:64px 16px}.library-empty h3{font-size:18px;margin:16px 0;color:#4a6051}.library-empty a{display:inline-flex;align-items:center;gap:5px;color:#397758;font-size:14px}@media(max-width:650px){.library-tabs{width:100%}.library-tabs button{flex:1;padding:8px}.library-item{padding:18px}.library-heading h2{font-size:22px}}
</style>
