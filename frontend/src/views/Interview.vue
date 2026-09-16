<template>
  <div class="interview-room">
    <header class="room-header">
      <div class="room-header-inner">
      <div class="room-brand"><span>M</span><div><strong>MianMian</strong><small>面面俱道 · 模拟面试</small></div></div>
      <div class="room-session-meta"><span :class="['connection-state', {online: connected}]">{{ connected ? '已连接' : '未连接' }}</span><span class="room-clock"><Clock3 :size="16" />{{ elapsed }}</span></div>
      <div class="room-account-actions"><button class="room-button end-button" :disabled="locked || loading || !active" @click="showFinish = true"><LogOut :size="16" />结束面试</button><LogoutButton :disabled="locked" /></div>
      </div>
    </header>

    <main class="room-main">
      <div v-if="loading" class="room-loading" role="status"><LoaderCircle class="spin" :size="24" />正在进入面试室…</div>
      <template v-else>
        <div class="room-heading"><div><p class="room-eyebrow">INTERVIEW ROOM</p><h1>{{ state.job_track || '技术面试' }}</h1></div><span>{{ styleLabel }}</span></div>
        <div class="room-progress"><span>已完成 {{ state.turn || 0 }} / {{ state.target_question_count || 0 }} 轮</span><progress aria-label="面试完成进度" :value="state.turn || 0" :max="state.target_question_count || 1" /></div>
        <div v-if="error" class="room-error" role="alert">{{ error }}</div>
        <div v-if="!connected && active" class="reconnect-row"><span>连接已断开，未发送的回答仍保留。</span><button class="room-button" @click="connect"><RefreshCw :size="16" />重新连接</button></div>
        <div v-if="!active && !state.session_id" class="reconnect-row"><button class="room-button" @click="load">重新加载</button><router-link to="/">返回工作台</router-link></div>

        <div v-if="state.session_id" class="room-layout">
          <section class="room-conversation">
            <div class="interviewer-label"><span class="interviewer-avatar"><AudioLines :size="22" /></span><div><strong>MianMian 面试官</strong><small>{{ busy ? '正在准备下一步…' : '等待你的回答' }}</small></div><span class="room-question-number">{{ String(Math.min((state.turn || 0) + 1, state.target_question_count)).padStart(2, '0') }}</span></div>
            <h2 class="room-question" tabindex="0">{{ state.question || '面试已结束' }}</h2>
            <div class="question-audio"><button class="room-button" :disabled="speechBusy || locked || !active" @click="speak"><LoaderCircle v-if="speechBusy" class="spin" :size="16" /><Volume2 v-else :size="16" />{{ speechBusy ? '正在合成…' : '朗读问题' }}</button><audio v-if="questionAudio" ref="questionPlayer" :src="questionAudio" controls /></div>

            <form class="room-composer" @submit.prevent="submit">
              <div class="composer-heading"><label for="interview-answer">你的回答</label><span :class="{overlimit: answer.length > MAX_ANSWER_CHARACTERS}">{{ answer.length }} / {{ MAX_ANSWER_CHARACTERS }}</span></div>
              <textarea id="interview-answer" v-model="answer" :disabled="busy || finishing || recording || transcribing || requestingMic || !active" placeholder="输入回答…" @keydown.ctrl.enter.prevent="submit" @keydown.meta.enter.prevent="submit" />
              <div v-if="recording" class="recording-status" role="status"><span class="recording-dot" /><AudioLines :size="20" /><strong>正在录音 {{ recordingTime }}</strong><span>最长 {{ duration(MAX_RECORDING_MS) }}</span></div>
              <p v-if="transcribing" class="voice-status" role="status"><LoaderCircle class="spin" :size="16" />正在转写语音，长录音可能需要几分钟，请稍候…</p>
              <p v-else-if="voiceNotice" class="voice-status" role="status">{{ voiceNotice }}</p>
              <div v-if="requestingMic" class="voice-status">等待麦克风授权<button type="button" class="room-button" @click="cancelMicRequest">取消</button></div>
              <div v-if="recordedUrl" class="recorded-preview"><audio :src="recordedUrl" controls aria-label="回听本次录音" /><button v-if="asrFailed" type="button" class="room-button" :disabled="locked" @click="transcribe"><RefreshCw :size="16" />重试转写</button></div>
              <div class="composer-footer"><button type="button" :class="['room-button', 'record-button', {recording}]" :disabled="busy || finishing || transcribing || requestingMic || speechBusy || !active" @click="toggleRecording"><Square v-if="recording" :size="16" /><Mic v-else :size="18" />{{ recording ? '停止并转写' : requestingMic ? '正在连接麦克风…' : '语音输入' }}</button><button type="submit" class="room-button send-answer" :disabled="!canSend"><LoaderCircle v-if="busy" class="spin" :size="18" /><Send v-else :size="17" />{{ busy ? '正在处理…' : '发送回答' }}</button></div>
            </form>
          </section>

          <aside class="room-transcript"><div class="transcript-heading"><h2>本场问答</h2><span>{{ state.history.length }} 轮</span></div><p v-if="!state.history.length" class="transcript-empty">暂无已完成的问答</p><details v-for="turn in state.history" :key="turn.turn" class="transcript-turn"><summary><span>{{ String(turn.turn).padStart(2, '0') }}</span>{{ turn.question }}<ChevronDown :size="14" /></summary><p>{{ turn.answer }}</p></details><div class="current-round"><span class="live-dot" />第 {{ Math.min(state.turn + 1, state.target_question_count) }} 轮 · {{ busy ? '处理中' : '进行中' }}</div></aside>
        </div>
      </template>
    </main>
    <div v-if="showFinish" class="room-dialog-backdrop" @click.self="!finishing && (showFinish = false)">
      <section class="room-dialog" role="alertdialog" aria-modal="true" aria-labelledby="finish-title" @keydown.esc="!finishing && (showFinish = false)"><h2 id="finish-title">结束本次面试？</h2><p>{{ state.turn ? `已完成 ${state.turn} 轮，结束后查看面试诊断。` : '尚未完成回答，结束后返回工作台。' }}</p><p v-if="answer.trim()">未发送的回答不会计入诊断。</p><p v-if="error" class="room-error" role="alert">{{ error }}</p><div><button class="room-button" :disabled="finishing" @click="showFinish = false">继续面试</button><button class="room-button send-answer" :disabled="finishing" @click="finish">{{ finishing ? '正在结束…' : '确认结束' }}</button></div></section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AudioLines, ChevronDown, Clock3, LoaderCircle, LogOut, Mic, RefreshCw, Send, Square, Volume2 } from 'lucide-vue-next'
import { API, request, wsUrl } from '../api'
import { styleName } from '../interviewStyles'
import LogoutButton from '../components/LogoutButton.vue'
import { MAX_RECORDING_MS, MAX_AUDIO_BYTES, MAX_ANSWER_CHARACTERS, RECORDING_AUDIO_BITRATE } from '../interviewLimits'

const route = useRoute(), router = useRouter(), id = route.params.id
const state = ref({history: [], turn: 0}), answer = ref(''), error = ref('')
const loading = ref(true), connected = ref(false), busy = ref(false), finishing = ref(false), showFinish = ref(false)
const recording = ref(false), requestingMic = ref(false), transcribing = ref(false), speechBusy = ref(false)
const recordedUrl = ref(''), questionAudio = ref(''), questionPlayer = ref(null), asrFailed = ref(false), voiceNotice = ref('')
const now = ref(Date.now()), recordStarted = ref(0)
const active = computed(() => state.value.status === 'IN_PROGRESS')
const locked = computed(() => busy.value || finishing.value || recording.value || requestingMic.value || transcribing.value)
const canSend = computed(() => connected.value && active.value && !locked.value && answer.value.trim().length > 0 && answer.value.length <= MAX_ANSWER_CHARACTERS)
const styleLabel = computed(() => styleName(state.value.style) || '项目与技术')
function duration(ms) { const seconds = Math.max(0, Math.floor(ms / 1000)); return `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}` }
const elapsed = computed(() => state.value.started_at ? duration(now.value - Date.parse(state.value.started_at)) : '00:00')
const recordingTime = computed(() => duration(now.value - recordStarted.value))
let socket, recorder, stream, recordTimeout, ticker, disposed = false, recordedBlob
let micRequest = 0
let speechController, speechVersion = 0
const controller = new AbortController()
function releaseUrl(target) { if (target.value) URL.revokeObjectURL(target.value); target.value = '' }
function stopQuestionAudio() {
  speechVersion++; speechController?.abort(); speechBusy.value = false
  questionPlayer.value?.pause(); questionPlayer.value?.removeAttribute('src'); questionPlayer.value?.load()
  releaseUrl(questionAudio)
}
function clearAudio() { stopQuestionAudio(); releaseUrl(recordedUrl); recordedBlob = null; asrFailed.value = false; voiceNotice.value = '' }
function applyState(data) {
  if (data.turn > state.value.turn) { answer.value = ''; clearAudio(); window.scrollTo({top:0, behavior:'smooth'}) }
  state.value = data
  if (data.status === 'COMPLETED') router.replace(data.turn ? `/report/${id}` : '/')
}
async function load() {
  loading.value = true; error.value = ''
  try { const data = await request(`/api/v1/interviews/${id}`, {signal: controller.signal}); if(disposed)return; applyState(data); if(data.status === 'IN_PROGRESS')connect() }
  catch(e) { if(!disposed)error.value = e.message }
  finally { loading.value = false }
}
function connect() {
  socket?.close(); connected.value = false
  const connection = new WebSocket(wsUrl(id)); socket = connection
  connection.onopen = () => { if(socket === connection) { connected.value = true; error.value = '' } }
  connection.onmessage = event => {
    if(socket !== connection || disposed)return
    try {
      const message = JSON.parse(event.data)
      if(message.type === 'SESSION_STATE') { applyState(message.payload); busy.value = false }
      if(message.type === 'PROCESSING')busy.value = true
      if(message.type === 'ANSWER_ACCEPTED') { answer.value = ''; clearAudio() }
      if(message.type === 'ERROR') { busy.value = false; error.value = message.message }
    } catch { busy.value = false; error.value = '连接数据异常，请重新连接' }
  }
  connection.onclose = () => { if(socket === connection) { connected.value = false; busy.value = false } }
  connection.onerror = () => { if(socket === connection) error.value = '连接失败，请重新连接面试' }
}
function submit() {
  if(!canSend.value)return
  if(socket?.readyState !== WebSocket.OPEN) { connected.value = false; return }
  stopQuestionAudio(); error.value = ''; busy.value = true
  socket.send(JSON.stringify({event:'ANSWER', text:answer.value, turn:state.value.turn}))
}
async function finish() {
  if(locked.value)return
  stopQuestionAudio()
  finishing.value = true; error.value = ''
  try { const data = await request(`/api/v1/interviews/${id}/finish`, {method:'POST', signal:controller.signal}); if(disposed)return; socket?.close(); applyState(data) }
  catch(e) { if(!disposed)error.value = e.message }
  finally { finishing.value = false }
}
async function speak() {
  if(speechBusy.value || locked.value || !active.value)return
  stopQuestionAudio(); speechController = new AbortController(); const current = speechVersion
  speechBusy.value = true; error.value = ''
  const question = state.value.question
  try {
    const body = new FormData(); body.append('text', question); if(state.value.interviewer_voice) body.append('voice', state.value.interviewer_voice); body.append('tone', state.value.interviewer_tone || 'professional')
    const token = localStorage.getItem('mianmian-token')
    const response = await fetch(API + '/api/v1/audio/tts', {method:'POST', body, signal:speechController.signal, headers:token ? {Authorization:`Bearer ${token}`} : {}})
    if(!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || '问题朗读失败') }
    const blob = await response.blob()
    if(disposed || current !== speechVersion || state.value.question !== question)return
    releaseUrl(questionAudio); questionAudio.value = URL.createObjectURL(blob)
    await nextTick(); await questionPlayer.value?.play().catch(() => {})
  } catch(e) { if(!disposed && current === speechVersion && e.name !== 'AbortError')error.value = e.message } finally { if(current === speechVersion)speechBusy.value = false }
}
async function transcribe() {
  if(!recordedBlob || transcribing.value)return
  transcribing.value = true; asrFailed.value = false; error.value = ''; voiceNotice.value = ''
  try {
    const mime = recordedBlob.type, ext = mime.includes('mp4') ? 'm4a' : mime.includes('ogg') ? 'ogg' : 'webm'
    const body = new FormData(); body.append('file', recordedBlob, `answer.${ext}`)
    const data = await request('/api/v1/audio/asr', {method:'POST', body, signal:controller.signal})
    if(disposed)return
    answer.value += (answer.value ? '\n' : '') + data.text
    voiceNotice.value = '转写完成，待确认发送'
    if(answer.value.length > MAX_ANSWER_CHARACTERS)error.value = `转写全文已保留，回答超过 ${MAX_ANSWER_CHARACTERS} 字符，请精简后发送。`
  } catch(e) { if(!disposed) { asrFailed.value = true; error.value = e.message; voiceNotice.value = '录音已保留，可重试转写' } }
  finally { transcribing.value = false }
}
async function toggleRecording() {
  if(recording.value) { if(recorder?.state === 'recording')recorder.stop(); return }
  if(locked.value)return
  stopQuestionAudio()
  requestingMic.value = true; error.value = ''; voiceNotice.value = ''
  const requestId = ++micRequest
  try {
    if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)throw new Error('当前浏览器不支持录音，请使用 HTTPS 或本机地址，并使用 Chrome / Edge。')
    questionPlayer.value?.pause()
    const acquiredStream = await navigator.mediaDevices.getUserMedia({audio:true})
    if(disposed || requestId !== micRequest) { acquiredStream.getTracks().forEach(t => t.stop()); return }
    stream = acquiredStream
    const mime = ['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t => MediaRecorder.isTypeSupported(t))
    const current = new MediaRecorder(stream, {audioBitsPerSecond:RECORDING_AUDIO_BITRATE, ...(mime ? {mimeType:mime} : {})}); recorder = current
    const chunks = []; let failed = false
    current.ondataavailable = e => { if(e.data.size)chunks.push(e.data) }
    current.onerror = () => { failed = true; error.value = '录音中断，请重新录制'; clearTimeout(recordTimeout); stream?.getTracks().forEach(t => t.stop()); recording.value = false }
    current.onstop = async () => {
      clearTimeout(recordTimeout); stream?.getTracks().forEach(t => t.stop()); recording.value = false
      if(disposed || failed)return
      recordedBlob = new Blob(chunks, {type:current.mimeType || mime || 'audio/webm'})
      if(!recordedBlob.size) { error.value = '未录到音频，请重新录制'; return }
      if(recordedBlob.size > MAX_AUDIO_BYTES) { error.value = '录音超过 25 MB，请缩短录音'; recordedBlob = null; return }
      releaseUrl(recordedUrl); recordedUrl.value = URL.createObjectURL(recordedBlob)
      await transcribe()
    }
    current.start(); releaseUrl(recordedUrl); recordedBlob = null; asrFailed.value = false
    recordStarted.value = Date.now(); now.value = Date.now(); recording.value = true
    recordTimeout = setTimeout(() => { if(current.state === 'recording')current.stop() }, MAX_RECORDING_MS)
  } catch(e) {
    if(requestId !== micRequest)return
    stream?.getTracks().forEach(t => t.stop()); recording.value = false
    if(!disposed)error.value = e.name === 'NotAllowedError' ? '麦克风权限被拒绝，请在浏览器中允许访问麦克风后重试。' : e.name === 'NotFoundError' ? '未检测到麦克风，请连接设备后重试。' : e.message
  } finally { if(requestId === micRequest)requestingMic.value = false }
}
function cancelMicRequest() { micRequest++; requestingMic.value = false; voiceNotice.value = '已取消麦克风连接' }
onMounted(() => { ticker = setInterval(() => { now.value = Date.now() }, 1000); load() })
onUnmounted(() => { disposed = true; controller.abort(); clearInterval(ticker); clearTimeout(recordTimeout); socket?.close(); if(recorder?.state === 'recording')recorder.stop(); stream?.getTracks().forEach(t => t.stop()); clearAudio() })
</script>

<style scoped>
.room-account-actions{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}
.interview-room{min-height:100vh;background:#f5f7f7;color:#202826;letter-spacing:0;font-family:inherit}
.room-header{margin:0;padding:16px var(--page-gutter);background:#fff;border-bottom:1px solid #dde5e2}
.room-header-inner{width:100%;max-width:1520px;margin-inline:auto;display:flex;align-items:center;gap:24px;min-width:0;flex-wrap:wrap}
.room-brand{display:flex;align-items:center;gap:12px}.room-brand>span{width:36px;height:36px;display:grid;place-items:center;background:#1b6b57;color:#fff;border-radius:8px;font-size:21px;font-weight:700}.room-brand strong{font-size:20px}.room-brand small{display:block;font-size:11px;color:#67756f;margin-top:3px}
.room-session-meta{display:flex;align-items:center;gap:24px;margin-left:auto;color:#64736c;font-size:13px}.room-clock{display:flex;gap:8px;align-items:center;font-variant-numeric:tabular-nums;min-width:72px}.connection-state:before,.live-dot{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;background:#b77943;margin-right:7px}.connection-state.online:before,.live-dot{background:#2b8067}
.room-button{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:1px solid #d6dfdc;border-radius:6px;background:white;color:#42554c;min-height:40px;padding:10px 14px;font-size:13px;font-weight:500;white-space:nowrap}.room-button:hover:not(:disabled){background:#eef4f1;border-color:#96b6a8}.room-button:disabled{opacity:.45;cursor:not-allowed}.room-button:focus-visible,textarea:focus-visible,summary:focus-visible{outline:3px solid #8fc5b1;outline-offset:3px}.end-button{color:#9b4a41}
.room-main{width:100%;min-width:0;max-width:calc(1520px + 2 * var(--page-gutter));margin:0 auto;padding:clamp(26px,3vw,48px) var(--page-gutter) 64px}.room-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.room-heading h1{font-size:clamp(24px,1.8vw,32px);line-height:1.4;letter-spacing:0;overflow-wrap:anywhere}.room-heading>div{min-width:0}.room-eyebrow{font-size:11px;font-weight:600;color:#78877f;margin-bottom:8px}.room-heading>span{font-size:13px;color:#65756c;border-left:2px solid #c0d9cd;padding-left:12px;flex-shrink:0}.room-progress{display:flex;align-items:center;gap:18px;margin:20px 0 28px;font-size:13px;color:#627269}.room-progress progress{margin:0;width:180px;height:5px;accent-color:#287860}
.room-layout{display:grid;grid-template-columns:minmax(0,1fr) 264px;gap:44px}.room-conversation{min-width:0}.interviewer-label{display:flex;align-items:center;gap:12px}.interviewer-avatar{display:grid;place-items:center;background:#e0eee7;color:#206449;width:44px;height:44px;border-radius:8px}.interviewer-label strong{font-size:14px}.interviewer-label small{display:block;color:#7b8881;font-size:12px;margin-top:5px}.room-question-number{font-size:30px;line-height:1;color:#c7d4cd;margin-left:auto;font-variant-numeric:tabular-nums}.room-question{font-size:22px;font-weight:500;line-height:1.65;letter-spacing:0;margin:24px 0 18px;overflow-wrap:anywhere;white-space:pre-wrap;max-height:260px;overflow:auto;scrollbar-width:thin}.question-audio{display:flex;align-items:center;flex-wrap:wrap;gap:12px;min-height:44px;margin-bottom:28px}.question-audio audio{height:36px;width:250px;max-width:100%}
.room-composer{border:1px solid #cedbd4;border-radius:8px;background:#fff;overflow:hidden;box-shadow:0 4px 18px #193a2705}.composer-heading{display:flex;justify-content:space-between;align-items:center;padding:18px 20px 0;font-size:12px;color:#809087}.composer-heading label{font-size:13px;color:#3b5045;font-weight:600}.composer-heading .overlimit{color:#b13e38}.room-composer textarea{width:100%;resize:vertical;min-height:230px;max-height:500px;border:0;background:transparent;padding:18px 20px;color:#273d30;font-size:15px;line-height:1.8;display:block;letter-spacing:0}.room-composer textarea::placeholder{color:#a3afa8}.composer-footer{border-top:1px solid #edf1ee;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px}.send-answer{background:#216c55;color:#fff;border-color:#216c55}.send-answer:hover:not(:disabled){background:#15523f;color:#fff}.record-button{background:#f3f7f4}.record-button.recording{color:#ab413a;border-color:#dfbcb8;background:#fff7f5}
.recording-status{display:flex;align-items:center;gap:10px;padding:12px 20px;color:#a74a40;font-size:12px;background:#fff5f2}.recording-status span:last-child{margin-left:auto;color:#977670}.recording-dot{width:7px;height:7px;background:#ba5248;border-radius:50%;animation:record-pulse 1s infinite}.voice-status{display:flex;align-items:center;gap:8px;padding:12px 20px;color:#4c7764;font-size:12px}.recorded-preview{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:0 18px 12px}.recorded-preview audio{max-width:100%;height:36px}
.room-transcript{border-left:1px solid #dde5e0;padding-left:26px;min-width:0}.transcript-heading{display:flex;justify-content:space-between;align-items:center;margin:12px 0 20px}.transcript-heading h2{font-size:14px;font-weight:600;letter-spacing:0}.transcript-heading>span{font-size:11px;color:#859389}.transcript-empty{font-size:13px;color:#9ba79f;padding:16px 0 28px}.transcript-turn{padding:16px 0;border-top:1px solid #e1e7e3}.transcript-turn summary{display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-size:12px;line-height:1.8;overflow-wrap:anywhere;list-style:none}.transcript-turn summary::-webkit-details-marker{display:none}.transcript-turn summary>span{color:#759885;font-size:11px}.transcript-turn summary svg{flex-shrink:0;margin-top:4px}.transcript-turn p{white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0 0;font-size:12px;line-height:1.9;color:#6f7f75}.current-round{padding-top:20px;border-top:1px solid #dce5df;font-size:12px;color:#4b7560}
.room-error{padding:14px 18px;margin:16px 0;background:#fff1ed;border:1px solid #f0d1c8;border-radius:6px;font-size:13px;line-height:1.7;color:#9e4437;overflow-wrap:anywhere}.reconnect-row{display:flex;align-items:center;gap:14px;margin:18px 0;font-size:13px;color:#916746}.room-loading{display:flex;align-items:center;justify-content:center;gap:12px;min-height:400px;color:#657c6c}.spin{animation:room-spin 1s linear infinite}
.room-dialog-backdrop{position:fixed;inset:0;z-index:100;display:grid;place-items:center;padding:20px;background:#142c2466}.room-dialog{background:#fff;border-radius:8px;padding:28px;width:100%;max-width:420px}.room-dialog h2{font-size:20px;letter-spacing:0;margin-bottom:16px}.room-dialog p{font-size:14px;color:#6c776f;line-height:1.8;margin-bottom:12px}.room-dialog>div{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}
@keyframes room-spin{to{transform:rotate(360deg)}}@keyframes record-pulse{50%{opacity:.35}}
.room-layout{grid-template-columns:minmax(0,1fr) minmax(260px,26%);gap:clamp(24px,3vw,48px)}
.room-question{font-size:clamp(21px,1.5vw,28px);max-height:none;overflow:visible;margin:22px 0 18px}
.room-composer textarea{min-height:clamp(180px,25vh,320px);max-height:60vh;font-size:16px}
.transcript-turn summary,.transcript-turn p{font-size:14px}
.reconnect-row,.recording-status,.voice-status{flex-wrap:wrap}.room-dialog{max-height:calc(100dvh - 40px);overflow-y:auto}.room-dialog>div{flex-wrap:wrap}
@media(max-width:900px){.room-header-inner{gap:14px}.room-layout{grid-template-columns:minmax(0,1fr);gap:32px}.room-transcript{border-left:0;border-top:1px solid #dde5e0;padding:20px 0 0}.room-session-meta{gap:12px}.connection-state{display:none}}
@media(max-width:600px){.room-header-inner{gap:16px}.room-brand small{font-size:10px}.room-brand strong{font-size:18px}.room-brand{gap:8px}.room-brand>span{width:32px;height:32px}.room-clock{min-width:60px;font-size:12px}.room-account-actions{width:100%;display:grid;grid-template-columns:1fr 1fr}.room-main{padding-bottom:40px}.room-heading h1{font-size:23px}.room-heading>span{font-size:12px}.composer-footer{padding:12px;flex-wrap:wrap}.composer-footer>button{flex:1 1 120px}.room-button{padding:10px 12px}.room-progress{gap:12px}.room-progress progress{flex:1;min-width:0}}
@media(prefers-reduced-motion:reduce){.spin,.recording-dot{animation:none}}
</style>
