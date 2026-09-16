<template>
  <section class="interview-panel teacher-page">
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
    <section ref="librarySection" class="draft-section"><h3>已入库 · {{ totalQuestions }} 道</h3>
      <label class="field">按适用岗位查看<select v-model="filterTrack" :disabled="libraryLoading" @change="changePage(1)"><option value="">全部岗位</option><option v-for="track in tracks" :key="track" :value="track">{{ track }}</option></select></label>
      <div v-if="totalQuestions" class="library-pagination" aria-label="题库分页">
        <span>每页 10 道 · 第 {{ page }} / {{ totalPages }} 页</span>
        <button class="secondary" :disabled="page <= 1 || libraryLoading" @click="changePage(page - 1)">上一页</button>
        <label>跳至 <select :value="page" :disabled="libraryLoading" aria-label="题库页码" @change="changePage(Number($event.target.value))"><option v-for="n in totalPages" :key="n" :value="n">第 {{ n }} 页</option></select></label>
        <button class="secondary" :disabled="page >= totalPages || libraryLoading" @click="changePage(page + 1)">下一页</button>
      </div>
      <p v-if="libraryLoading" class="notice" role="status">正在加载题目…</p>
      <p v-if="libraryError" class="error" role="alert">{{ libraryError }} <button class="secondary" @click="changePage(page)">重试</button></p>
      <p v-if="!totalQuestions && !libraryLoading && !libraryError" class="description">还没有题目。导入并确认后，学员就能选择这些题目练习。</p>
      <article v-for="q in questions" :key="q.id" class="library-item">
        <span class="pill">{{ q.category }} · {{ q.difficulty }}</span><h4>{{ q.question }}</h4><p class="description">{{ q.job_track }} · {{ q.source_file }}</p>
        <form v-if="answerEdits[q.id] !== undefined" @submit.prevent="saveAnswer(q)">
          <label class="field">适用岗位<input v-model.trim="trackEdits[q.id]" required maxlength="100" list="job-tracks" :disabled="answerSaving[q.id]" /></label>
          <label class="field">参考答案<textarea v-model="answerEdits[q.id]" maxlength="12000" :disabled="answerSaving[q.id]" placeholder="填写或修改参考答案，可留空" /></label>
          <small>{{ answerEdits[q.id].length }} / 12000</small>
          <button class="secondary ai-answer-button" type="button" :disabled="answerSaving[q.id] || answerSuggesting[q.id]" @click="suggestAnswer(q)">{{ answerSuggesting[q.id] ? '正在生成参考答案…' : '让大模型生成参考答案' }}</button>
          <small class="field-help">生成后会填入编辑框，你可以修改后再保存；调用会计入当前教师 Token 账单。</small>
          <div class="answer-edit-actions"><button class="primary" type="submit" :disabled="answerSaving[q.id]">{{ answerSaving[q.id] ? '正在保存…' : '保存答案' }}</button><button class="secondary" type="button" :disabled="answerSaving[q.id]" @click="cancelAnswer(q.id)">取消</button></div>
        </form>
        <template v-else>
          <details v-if="q.answer"><summary>参考答案</summary><pre class="source-text">{{ q.answer }}</pre></details><small v-else>未提供参考答案</small>
          <button class="secondary" @click="editAnswer(q)">编辑答案与岗位</button>
        </template>
        <p v-if="answerErrors[q.id]" class="error" role="alert">{{ answerErrors[q.id] }}</p>
        <p v-if="answerNotices[q.id]" class="notice" role="status">{{ answerNotices[q.id] }}</p>
      </article>
      <div v-if="totalPages > 1" class="library-pagination"><span>第 {{ page }} / {{ totalPages }} 页</span><button class="secondary" :disabled="page <= 1 || libraryLoading" @click="changePage(page - 1)">上一页</button><button class="secondary" :disabled="page >= totalPages || libraryLoading" @click="changePage(page + 1)">下一页</button></div>
    </section>
  </section>
</template>
<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { request, importQuestions } from '../api'
const importing = ref(false), saving = ref(false), busy = computed(() => importing.value || saving.value)
const importStatus = ref(''), importPercent = ref(null), importProgress = ref({}), commitError = ref(''), savedCount = ref(null)
const savedStatus = ref(null)
let importController
const jobTrack = ref('AI 应用开发工程师'), error = ref(''), notice = ref(''), draft = ref(null), questions = ref([])
const page = ref(1), totalQuestions = ref(0), libraryLoading = ref(false), libraryError = ref(''), librarySection = ref(null)
const totalPages = computed(() => Math.max(1, Math.ceil(totalQuestions.value / 10)))
const answerEdits = ref({}), answerSaving = ref({}), answerErrors = ref({}), answerNotices = ref({})
const answerSuggesting = ref({})
const trackEdits = ref({}), tracks = ref([]), filterTrack = ref('')
const validDraft = computed(() => draft.value?.questions.length && draft.value.questions.every(q => q.question.trim() && q.source_quote.trim()))
const draftDuplicateCount = computed(() => {
  if (!draft.value) return 0
  const seen = new Set(); let duplicates = 0
  for (const q of draft.value.questions) { const key = (q.question || '').replace(/\s+/g, '').trim().toLocaleLowerCase(); if (key && seen.has(key)) duplicates++; seen.add(key) }
  return duplicates
})
async function load(targetPage = page.value) {
  libraryLoading.value = true; libraryError.value = ''
  try {
    const data = await request(`/api/v1/teacher/question-bank?page=${targetPage}${filterTrack.value ? `&job_track=${encodeURIComponent(filterTrack.value)}` : ''}`)
    tracks.value = data.tracks
    questions.value = data.items; totalQuestions.value = data.total; page.value = data.page
  } catch (e) { libraryError.value = e.message; throw e } finally { libraryLoading.value = false }
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
    try { await load(1) } catch (e) { error.value = `入库已成功，但列表刷新失败：${e.message}` }
    await nextTick(); savedStatus.value?.scrollIntoView({behavior: 'smooth', block: 'center'})
  } catch (e) { commitError.value = e.message; error.value = `入库失败：${e.message}。校对内容已保留，可重试。` } finally { saving.value = false }
}
onUnmounted(() => importController?.abort())
onMounted(async () => { try { await load() } catch (e) { error.value = e.message } })
</script>
