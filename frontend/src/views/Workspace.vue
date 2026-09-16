<template>
  <div class="workspace">
    <section class="hero"><div><span class="pill">AI 应用开发 · 专项训练</span><h2>把每次回答，<em>练成你的优势。</em></h2><p>上传简历，围绕你的项目经历进行提问、追问与复盘。</p><div class="hero-actions"><button class="primary" :disabled="busy" @click="startInterview">{{ busy ? '正在准备…' : '开始本次面试 →' }}</button><button class="secondary" :disabled="busy" @click="showConfig = true">简历与训练设置</button></div></div><div class="hero-orbit"><div class="orbit-ring"/><div class="orb-main">M</div></div></section>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <section class="interview-panel history-panel">
      <div class="panel-head"><div><span class="section-kicker">MY INTERVIEWS</span><h3>{{ selectedDate ? `${selectedDate} 的面试` : '我的面试记录' }}</h3></div><div class="history-actions"><button v-if="selectedDate" class="secondary" @click="router.push('/')">全部记录</button><button class="secondary" :disabled="historyLoading" @click="refreshHistory">刷新</button></div></div>
      <p class="description">按开始时间倒序 · {{ filteredHistory.length }} 场</p>
      <p v-if="historyLoading" class="notice" role="status">正在加载面试记录…</p>
      <p v-else-if="historyError" class="error" role="alert">{{ historyError }}</p>
      <p v-else-if="!filteredHistory.length" class="history-empty">{{ selectedDate ? '当天还没有模拟面试，换个日期看看吧。' : '还没有面试记录，从第一场练习开始吧。' }}</p>
      <article v-for="item in filteredHistory" :key="item.session_id" class="history-entry">
        <component :is="item.has_report ? RouterLink : 'div'" :to="item.has_report ? `/report/${item.session_id}` : undefined" class="history-date" :aria-label="item.has_report ? `${item.date} ${formatTime(item.started_at)} 的面试报告` : undefined"><span>{{ item.date.slice(0,4) }}</span><strong>{{ item.date.slice(5).replace('-', '.') }}</strong><span>{{ formatTime(item.started_at) }}</span></component>
        <div class="history-info"><h4>{{ item.job_track }}</h4><p>{{ styleName(item.style) }} · 已完成 {{ item.turn }} / {{ item.target_question_count }} 轮</p><span :class="['history-status', {ongoing:item.status === 'IN_PROGRESS'}]">{{ item.status === 'IN_PROGRESS' ? '进行中' : '已结束' }}</span></div>
        <router-link v-if="item.has_report" :to="`/report/${item.session_id}`" class="secondary history-link" :aria-label="`${item.date} ${formatTime(item.started_at)} 查看面试诊断`">查看面试诊断 →</router-link>
        <router-link v-else-if="item.status === 'IN_PROGRESS'" :to="`/interview/${item.session_id}`" class="secondary history-link">继续面试 →</router-link>
        <span v-else class="history-unavailable">未完成回答，暂无报告</span>
      </article>
    </section>

    <div v-if="showConfig" class="modal-backdrop" @click.self="!uploading && !busy && (showConfig = false)"><div class="modal config-modal"><div class="config-title"><span class="section-kicker">TRAINING SETUP</span><h3>简历与训练设置</h3><p>先完善训练条件，面试官会据此调整问题方向和难度。</p></div>
      <p v-if="uploadError" class="error" role="alert">{{ uploadError }}</p>
      <section class="material-section resume-section" aria-labelledby="resume-heading" :aria-busy="uploadKind === 'resume'">
        <div class="material-heading"><div><h4 id="resume-heading">个人简历</h4><span class="material-requirement">简历 / 项目经历，二选一</span></div><span :class="['material-status', { ready: resumeId || resumeText.trim() }]" role="status"><CheckCircle2 v-if="resumeId || resumeText.trim()" :size="15" />{{ resumeId ? '已上传' : resumeText.trim() ? '已填写经历' : '待完善' }}</span></div>
        <input ref="resumeInput" class="resume-file-input" type="file" accept=".pdf,.docx" hidden :disabled="uploading || busy" @change="uploadResume" />
        <div v-if="resumeId" class="material-file resume-file">
          <FileText class="file-symbol" :size="24" />
          <div class="file-info"><strong>{{ resumeName }}</strong><span>解析完成 · {{ resumeText.length.toLocaleString() }} 字 · 本次面试使用</span></div>
          <div class="file-tools"><button type="button" class="file-tool" title="更换简历" aria-label="更换简历" :disabled="uploading || busy" @click="resumeInput?.click()"><RefreshCw :size="17" /></button><button type="button" class="file-tool" title="移除简历" aria-label="移除简历" :disabled="uploading || busy" @click="clearResume"><Trash2 :size="17" /></button></div>
        </div>
        <div v-else-if="uploadKind !== 'resume'" class="material-empty"><FileText :size="26" /><div><strong>尚未上传简历</strong><span>PDF / DOCX · 最大 10 MB</span></div><button type="button" class="secondary upload-command" :disabled="uploading || busy" @click="resumeInput?.click()"><Upload :size="16" />上传简历</button></div>
        <div v-if="uploadKind === 'resume'" class="material-pending" role="status"><LoaderCircle class="upload-spinner" :size="18" /><div><strong>{{ pendingFile }}</strong><span>正在上传并解析简历…</span></div></div>
        <p v-if="resumeError" class="error" role="alert">{{ resumeError }}</p>
        <details v-if="resumeId" class="material-details"><summary>查看简历内容</summary><pre class="source-text">{{ resumeText }}</pre></details>
        <label v-else class="field manual-experience">或填写项目经历<textarea v-model="resumeText" maxlength="80000" :disabled="busy || uploading" placeholder="介绍你参与的项目、负责的工作和取得的成果" /></label>
      </section>
      <section class="material-section knowledge-section" aria-labelledby="knowledge-heading" :aria-busy="uploadKind === 'knowledge'">
        <div class="material-heading"><div><h4 id="knowledge-heading">本次临时知识库 <span class="optional-label">可选</span></h4><span class="material-requirement">仅本次使用，不加入公共题库</span></div><span :class="['material-status', { ready: knowledgeFiles.length }]" role="status">{{ knowledgeFiles.length ? `已上传 ${knowledgeFiles.length} 份` : '未添加' }}</span></div>
        <input ref="knowledgeInput" class="knowledge-file-input" type="file" accept=".md,.markdown,.pdf,.docx" hidden :disabled="uploading || busy" @change="uploadKnowledge" />
        <div v-if="!knowledgeFiles.length && uploadKind !== 'knowledge'" class="material-empty knowledge-empty"><Library :size="26" /><div><strong>不上传也可以开始面试</strong><span>Markdown / PDF / DOCX · 最大 10 MB</span></div><button type="button" class="secondary upload-command" :disabled="uploading || busy" @click="knowledgeInput?.click()"><Plus :size="16" />添加资料</button></div>
        <article v-for="file in knowledgeFiles" :key="file.id" class="material-file knowledge-file">
          <FileText class="file-symbol" :size="24" /><div class="file-info"><strong>{{ file.name }}</strong><span>解析完成 · {{ file.questionIds.length }} 道题 · 已选 {{ selectedCount(file) }} 道</span></div>
          <button type="button" class="file-tool" :title="`移除 ${file.name}`" :aria-label="`移除知识库 ${file.name}`" :disabled="uploading || busy" @click="removeKnowledge(file)"><Trash2 :size="17" /></button>
        </article>
        <div v-if="uploadKind === 'knowledge'" class="material-pending" role="status"><LoaderCircle class="upload-spinner" :size="18" /><div><strong>{{ pendingFile }}</strong><span>正在上传并提取题目…</span></div></div>
        <p v-if="knowledgeError" class="error" role="alert">{{ knowledgeError }}</p>
        <div v-if="knowledgeFiles.length" class="knowledge-footer"><span :class="{ 'selection-pending': !selectedIds.length }">{{ selectedIds.length ? `本次已选 ${selectedIds.length} 道临时题目` : '尚未选题，本次暂不使用这些资料' }}</span><button type="button" class="secondary upload-command" :disabled="uploading || busy" @click="knowledgeInput?.click()"><Plus :size="16" />继续添加</button></div>
        <details v-if="bank.length" class="material-details temporary-questions"><summary>选择本次使用的题目 · {{ selectedIds.length }} / {{ bank.length }}</summary><fieldset class="question-selection"><legend>临时题目（最多选择 20 道）</legend><label v-for="q in bank" :key="q.id"><input type="checkbox" :value="q.id" v-model="selectedIds" :disabled="busy || uploading || (!selectedIds.includes(q.id) && selectedIds.length >= 20)" />{{ q.question }}</label></fieldset></details>
      </section>
      <label class="field">目标岗位<input v-model="jobTrack" maxlength="100" :disabled="busy" /></label>
      <div class="field-grid"><label class="field setting-field"><span>面试风格</span><select v-model="style" :disabled="busy"><option v-for="item in interviewStyles" :key="item.value" :value="item.value">{{ item.label }}</option></select><small class="field-help">{{ styleDescription }}</small></label><label class="field setting-field"><span>面试轮数</span><select v-model.number="totalQuestions" :disabled="busy"><option :value="3">3 轮</option><option :value="5">5 轮</option><option :value="8">8 轮</option></select><small class="field-help">控制本次练习的完整程度。</small></label></div>
      <label class="field setting-field"><span>工作年限</span><select v-model="experienceYears" :disabled="busy"><option v-for="item in experienceOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select><small class="field-help">用于匹配适合当前经验阶段的题目难度。</small></label>
      <div class="field-grid"><div class="field setting-field"><span>面试官音色</span><select v-model="interviewerVoice" :disabled="busy || previewBusy"><option value="">系统默认</option><option value="female">女声</option><option value="male">男声</option></select><small class="field-help">选择面试官的声音，点击试听感受效果。</small><button type="button" class="secondary preview-button" :disabled="busy || previewBusy" @click="previewVoice">{{ previewBusy ? '正在生成试听…' : '试听当前音色' }}</button><audio v-if="previewAudio" ref="previewPlayer" :src="previewAudio" controls aria-label="面试官音色试听" /></div><label class="field setting-field"><span>面试官语气</span><select v-model="interviewerTone" :disabled="busy || previewBusy"><option value="professional">专业稳重</option><option value="friendly">亲切自然</option><option value="pressing">追问感强</option><option value="concise">简洁利落</option></select><small class="field-help">不改变题目难度；部分音频模型通过朗读节奏体现语气。</small></label></div>
      <QuestionExpression v-model="questionExpression" :disabled="busy" />
      <fieldset class="question-selection"><legend>题库适用岗位（可多选，最多 10 个）</legend><p v-if="!tracks.length" class="description">暂无已入库的岗位题库</p><label v-for="track in tracks" :key="track.job_track"><input type="checkbox" :value="track.job_track" v-model="selectedTracks" :disabled="busy || (!selectedTracks.includes(track.job_track) && selectedTracks.length >= 10)" />{{ track.job_track }} <small>· {{ track.question_count }} 道题</small></label></fieldset>
      <p class="description">{{ selectedTracks.length ? `已选 ${selectedTracks.length} 个岗位题库。` : '未选择时，围绕简历与目标岗位出题。' }}系统会从所选岗位均衡抽取本场参考题，再结合简历与回答追问。</p>
      <div class="modal-actions"><button class="secondary" :disabled="uploading || busy" @click="showConfig = false">保存设置</button><button class="primary" :disabled="uploading || busy" @click="startInterview">{{ busy ? '正在准备…' : '开始面试' }}</button></div>
    </div></div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { API, request } from '../api'
import { interviewStyles, styleName } from '../interviewStyles'
import { historyItems, historyLoading, historyError, refreshHistory } from '../studentHistory'
import QuestionExpression from '../components/QuestionExpression.vue'
import { CheckCircle2, FileText, Library, LoaderCircle, Plus, RefreshCw, Trash2, Upload } from 'lucide-vue-next'
const router = useRouter(), route = useRoute()
const jobTrack = ref('AI 应用开发工程师'), style = ref('HARDCORE'), totalQuestions = ref(5), experienceYears = ref('1-3'), interviewerVoice = ref(''), interviewerTone = ref('professional')
const questionExpression = ref(3)
const experienceOptions=[{value:'1',label:'1 年'},{value:'1-3',label:'1～3 年'},{value:'3-5',label:'3～5 年'},{value:'5-7',label:'5～7 年'},{value:'7+',label:'7 年以上'}]
const styleDescriptions={HARDCORE:'围绕工程细节连续追问，适合检验技术深度。',GUIDING:'循序渐进地提示思路，帮助你建立完整回答。',BUSINESS:'聚焦业务目标、用户价值和落地结果。',CREATIVE:'AI 非常规问题与跨领域联想，考查创造力和边界意识。',ALL_ROUND:'业务场景与技术深挖结合，难度偏高。'}
const styleDescription=computed(()=>styleDescriptions[style.value])
const resumeId = ref(''), resumeName = ref(''), resumeText = ref(''), bank = ref([]), selectedIds = ref([])
const tracks = ref([]), selectedTracks = ref([])
const showConfig = ref(false), busy = ref(false), uploadError = ref(''), error = ref(''), previewBusy = ref(false), previewAudio = ref('')
const uploadKind = ref(''), pendingFile = ref(''), resumeError = ref(''), knowledgeError = ref(''), knowledgeFiles = ref([])
const uploading = computed(() => Boolean(uploadKind.value))
const resumeInput = ref(null), knowledgeInput = ref(null)
const selectedDate = computed(() => typeof route.query.date === 'string' ? route.query.date : '')
const filteredHistory = computed(() => historyItems.value.filter(item => !selectedDate.value || item.date === selectedDate.value))
const formatTime = value => new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value))
let disposed = false
const controller = new AbortController()
const previewPlayer = ref(null)
let previewController, previewVersion = 0
function stopPreview() {
  previewVersion++; previewController?.abort(); previewBusy.value = false
  previewPlayer.value?.pause(); previewPlayer.value?.removeAttribute('src'); previewPlayer.value?.load()
  if (previewAudio.value) URL.revokeObjectURL(previewAudio.value)
  previewAudio.value = ''
}
watch(showConfig, value => { if (!value) stopPreview() }, {flush:'sync'})
watch([interviewerVoice, interviewerTone], stopPreview, {flush:'sync'})
async function previewVoice() {
  if (previewBusy.value) return
  stopPreview(); previewController = new AbortController(); const current = previewVersion
  previewBusy.value = true; uploadError.value = ''
  try {
    const body = new FormData(); body.append('text', '你好，我是本场面试官。我们先从你的项目经历开始，请用几句话介绍你负责的部分。'); body.append('voice', interviewerVoice.value); body.append('tone', interviewerTone.value)
    const token = localStorage.getItem('mianmian-token')
    const response = await fetch(API + '/api/v1/audio/tts', {method:'POST', body, signal:previewController.signal, headers:token ? {Authorization:`Bearer ${token}`} : {}})
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || '试听生成失败') }
    const blob = await response.blob()
    if (disposed || current !== previewVersion || !showConfig.value) return
    previewAudio.value = URL.createObjectURL(blob)
  } catch (e) { if (!disposed && current === previewVersion && e.name !== 'AbortError') uploadError.value = `试听失败：${e.message}` }
  finally { if (current === previewVersion) previewBusy.value = false }
}
async function uploadResume(e) {
  const file = e.target.files?.[0]; e.target.value = ''; if(!file || uploading.value || busy.value)return
  uploadKind.value = 'resume'; pendingFile.value = file.name; uploadError.value = ''; resumeError.value = ''
  try {
    const body = new FormData(); body.append('file',file)
    const data = await request('/api/v1/resumes',{method:'POST',body,signal:controller.signal})
    if(disposed)return
    resumeId.value = data.resume_id; resumeName.value = data.filename; resumeText.value = data.text
  } catch(e) { if(!disposed)resumeError.value = `简历上传失败：${e.message}` }
  finally { uploadKind.value = ''; pendingFile.value = '' }
}
async function uploadKnowledge(e) {
  const file = e.target.files?.[0]; e.target.value = ''; if(!file || uploading.value || busy.value)return
  uploadKind.value = 'knowledge'; pendingFile.value = file.name; uploadError.value = ''; knowledgeError.value = ''
  try {
    const body = new FormData(); body.append('file',file)
    const data = await request('/api/v1/student/knowledge/import',{method:'POST',body,signal:controller.signal})
    if(disposed)return
    const questions = data.questions.map((q,i) => ({...q,id:`temp-${data.knowledge_id}-${i}`}))
    bank.value.push(...questions)
    knowledgeFiles.value.push({id:data.knowledge_id,name:data.filename || file.name,questionIds:questions.map(q => q.id)})
  } catch(e) { if(!disposed)knowledgeError.value = `知识库上传失败：${e.message}` }
  finally { uploadKind.value = ''; pendingFile.value = '' }
}
function clearResume() { resumeId.value = ''; resumeName.value = ''; resumeText.value = ''; resumeError.value = '' }
function selectedCount(file) { return file.questionIds.filter(id => selectedIds.value.includes(id)).length }
function removeKnowledge(file) {
  bank.value = bank.value.filter(q => !file.questionIds.includes(q.id))
  selectedIds.value = selectedIds.value.filter(id => !file.questionIds.includes(id))
  knowledgeFiles.value = knowledgeFiles.value.filter(item => item.id !== file.id)
}
async function startInterview() {
  if(busy.value || uploading.value)return
  if(!resumeId.value && !resumeText.value.trim()) { showConfig.value = true; uploadError.value = '请上传简历，或填写项目经历后开始'; return }
  stopPreview(); busy.value = true; error.value = ''; uploadError.value = ''
  try {
    const data = await request('/api/v1/interviews',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({job_track:jobTrack.value,interviewer_style:style.value,experience_years:experienceYears.value,interviewer_voice:interviewerVoice.value,interviewer_tone:interviewerTone.value,question_expression:questionExpression.value,resume_id:resumeId.value || null,resume_text:resumeId.value ? '' : resumeText.value,target_question_count:totalQuestions.value,knowledge_tracks:selectedTracks.value,temporary_questions:bank.value.filter(q => selectedIds.value.includes(q.id))})})
    if(disposed)return
    router.push(`/interview/${data.session_id}`)
  } catch(e) { if(!disposed) { error.value = e.message; uploadError.value = e.message } } finally { busy.value = false }
}
onMounted(async () => {
  try { tracks.value = (await request('/api/v1/student/question-tracks',{signal:controller.signal})).items } catch(e) { if(!disposed)error.value = e.message }
})
onBeforeUnmount(() => { disposed = true; controller.abort(); stopPreview() })
</script>
<style scoped>
.history-panel { margin-top: clamp(24px, 2vw, 36px); }
.history-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.history-entry { display: grid; grid-template-columns: 80px minmax(0, 1fr) auto; align-items: center; gap: clamp(16px, 2vw, 32px); padding: clamp(22px, 2vw, 32px) 0; border-top: 1px solid #eceee9; }
.history-date { display: grid; gap: 6px; text-decoration: none; }
.history-date strong { font-size: 22px; color: #394d43; font-weight: 500; }
.history-date span { font-size: 12px; color: #8d978e; }
a.history-date:hover strong { color: #d76a42; }
a.history-date:focus-visible { outline: 2px solid #d76a42; outline-offset: 5px; border-radius: 4px; }
.history-info { min-width: 0; }
.history-info h4 { font-size: clamp(16px, 1.2vw, 20px); margin-bottom: 7px; }
.history-info p { font-size: 14px; color: #899187; line-height: 1.8; }
.history-status { display: inline-block; margin-top: 8px; font-size: 12px; color: #8c958a; }
.history-status.ongoing { color: #b4753e; }
.history-link { text-decoration: none; font-size: 14px; white-space: nowrap; }
.history-unavailable { font-size: 13px; color: #959b91; max-width: 180px; overflow-wrap: anywhere; }
.history-empty { padding: 45px 0; color: #8e978d; font-size: 14px; }
@media (max-width: 650px) {
  .history-entry { grid-template-columns: 64px minmax(0, 1fr); gap: 12px 16px; }
  .history-link, .history-unavailable { grid-column: 2; justify-self: start; max-width: 100%; white-space: normal; }
  .history-date strong { font-size: 20px; }
  .history-actions { gap: 6px; }
}
</style>
<style scoped>
.config-title { padding-bottom: 18px; border-bottom: 1px solid #ece9e2; margin-bottom: 20px; }
.config-title h3 { margin: 6px 0 8px; }
.config-title p { color: #858b82; font-size: 13px; line-height: 1.7; }
.setting-field { margin: 12px 0 18px; }
.setting-field > span { display: block; font-weight: 600; color: #4f5d53; }
.setting-field select { margin-top: 8px; }
.field-help { display: block; color: #969c92; font-size: 12px; line-height: 1.6; margin-top: 7px; }
.preview-button { margin-top: 10px; font-size: 12px; }
.setting-field audio { display: block; width: min(100%, 300px); height: 34px; margin-top: 10px; }
.material-section { padding: 4px 0 22px; border-bottom: 1px solid #e1e6e1; margin-bottom: 22px; min-width: 0; }
.material-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.material-heading h4 { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 15px; color: #344c41; margin: 0 0 6px; }
.material-requirement { font-size: 12px; color: #7c877f; line-height: 1.6; }
.material-status { display: inline-flex; align-items: center; gap: 5px; flex-shrink: 0; border-radius: 20px; padding: 5px 9px; background: #f0f2ef; color: #7d887f; font-size: 12px; }
.material-status.ready { color: #347358; background: #e9f3ed; }
.optional-label { padding: 2px 7px; border: 1px solid #d9dfe0; border-radius: 5px; font-size: 11px; font-weight: 400; color: #74828a; background: #fff; }
.material-empty { display: flex; align-items: center; gap: 14px; padding: 18px; border: 1px dashed #d4ddd4; border-radius: 8px; background: #fafbf8; }
.material-empty > svg { flex-shrink: 0; color: #8a9b8b; }
.material-empty > div { flex: 1; min-width: 0; }
.material-empty strong { display: block; font-weight: 500; color: #536252; font-size: 13px; margin-bottom: 6px; }
.material-empty span { color: #899186; font-size: 12px; line-height: 1.7; }
.upload-command { display: inline-flex; align-items: center; justify-content: center; gap: 7px; font-size: 12px; padding: 9px 12px; flex-shrink: 0; }
.material-file { display: flex; align-items: center; gap: 13px; padding: 16px; border: 1px solid #d8e7dc; border-radius: 8px; background: #f1f7f2; }
.file-symbol { color: #548168; flex-shrink: 0; }
.file-info { flex: 1; min-width: 0; }
.file-info strong { display: block; color: #355e47; font-size: 14px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.file-info span { display: block; color: #668272; font-size: 12px; line-height: 1.8; margin-top: 4px; }
.file-tools { display: flex; gap: 2px; flex-shrink: 0; }
.file-tool { display: inline-flex; align-items: center; justify-content: center; padding: 8px; background: transparent; border: 0; border-radius: 6px; color: #74877b; cursor: pointer; flex-shrink: 0; }
.file-tool:hover { background: #e2ece4; color: #345c44; }
.file-tool:focus-visible { outline: 2px solid #377e6b; outline-offset: 2px; }
.material-details { margin: 14px 0 0; }
.material-details summary { font-size: 12px; color: #53775f; line-height: 1.8; }
.manual-experience { margin-bottom: 0; color: #7c877f; font-size: 12px; }
.manual-experience textarea { min-height: 88px; font-size: 13px; }
.knowledge-empty { background: transparent; border-color: #dce1df; }
.knowledge-file + .knowledge-file { margin-top: 10px; }
.knowledge-footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-top: 14px; }
.knowledge-footer > span { color: #527b61; font-size: 12px; line-height: 1.7; }
.knowledge-footer .selection-pending { color: #9b753d; }
.temporary-questions .question-selection { margin-top: 12px; background: #fff; }
.material-pending { display: flex; align-items: center; gap: 12px; padding: 16px; margin-top: 12px; border-radius: 8px; background: #f4f6f4; color: #657c68; }
.material-pending > div { min-width: 0; }
.material-pending strong { display: block; font-size: 13px; overflow-wrap: anywhere; line-height: 1.6; }
.material-pending span { display: block; font-size: 12px; margin-top: 4px; }
.upload-spinner { flex-shrink: 0; animation: upload-spin 1s linear infinite; }
@keyframes upload-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .upload-spinner { animation: none; } }
@media (max-width: 650px) {
  .material-empty { flex-wrap: wrap; padding: 14px; gap: 12px; }
  .material-empty .upload-command { width: 100%; }
  .material-file { padding: 12px; gap: 9px; flex-wrap: wrap; }
  .file-info { flex-basis: calc(100% - 40px); }
  .file-tools, .knowledge-file > .file-tool { margin-left: auto; }
  .manual-experience textarea { font-size: 16px; }
}
</style>
