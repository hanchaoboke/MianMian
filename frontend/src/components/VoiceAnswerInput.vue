<template>
  <div class="voice-input">
    <div class="voice-actions">
      <button type="button" class="secondary" :class="{ recording }" :disabled="disabled || requesting || transcribing" @click="toggleRecording">
        <Square v-if="recording" :size="16" /><Mic v-else :size="18" />{{ recording ? '停止并转写' : '语音输入' }}
      </button>
      <span v-if="recording" role="status">正在录音 {{ elapsed }} · 最长 {{ duration(MAX_RECORDING_MS) }}</span>
      <span v-else-if="requesting" role="status">等待麦克风授权 <button type="button" class="secondary" @click="cancelPermission">取消</button></span>
      <span v-else-if="transcribing" role="status">正在转写语音，请稍候…</span>
      <span v-else>最长 {{ duration(MAX_RECORDING_MS) }}，转写后可编辑，再提交对比。</span>
    </div>
    <p v-if="error" class="voice-error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <div v-if="recordedUrl" class="voice-preview">
      <audio ref="player" :src="recordedUrl" controls aria-label="回听本次重答录音" />
      <button v-if="asrFailed" type="button" class="secondary" :disabled="disabled || busy" @click="transcribe">重试转写</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Mic, Square } from 'lucide-vue-next'
import { request } from '../api'
import { MAX_RECORDING_MS, MAX_AUDIO_BYTES, RECORDING_AUDIO_BITRATE } from '../interviewLimits'

const props = defineProps({ disabled: Boolean })
const emit = defineEmits(['transcript', 'busy'])
const recording = ref(false), requesting = ref(false), transcribing = ref(false)
const error = ref(''), notice = ref(''), asrFailed = ref(false), recordedUrl = ref(''), player = ref(null)
const elapsedMs = ref(0), busy = computed(() => recording.value || requesting.value || transcribing.value)
const elapsed = computed(() => duration(elapsedMs.value))
let recorder, stream, blob, timer, ticker, asrController, generation = 0, disposed = false
watch(busy, value => emit('busy', value), { flush: 'sync' })
function duration(ms) {
  const seconds = Math.floor(ms / 1000)
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}
function stopTracks() { stream?.getTracks().forEach(track => track.stop()); stream = null }
function clearTimers() { clearTimeout(timer); clearInterval(ticker) }
function clearPreview() {
  player.value?.pause()
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordedUrl.value = ''
}
function cancelPermission() { generation++; requesting.value = false; notice.value = '已取消麦克风连接' }
async function transcribe() {
  if (!blob || busy.value || props.disabled || disposed) return
  const current = generation
  transcribing.value = true; asrFailed.value = false; error.value = ''; notice.value = ''
  asrController = new AbortController()
  try {
    const ext = blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'
    const body = new FormData(); body.append('file', new File([blob], `answer.${ext}`, { type: blob.type }))
    const data = await request('/api/v1/audio/asr', { method: 'POST', body, signal: asrController.signal })
    if (disposed || current !== generation) return
    if (typeof data.text !== 'string' || !data.text.trim()) throw new Error('未识别到语音，请重新录音')
    emit('transcript', data.text.trim())
    notice.value = '转写完成，请检查文字后提交。'
  } catch (e) {
    if (!disposed && current === generation) {
      asrFailed.value = true; error.value = e.message; notice.value = '录音已保留，可回听或重试转写。'
    }
  } finally { if (current === generation) transcribing.value = false }
}
async function toggleRecording() {
  if (recording.value) { if (recorder?.state === 'recording') recorder.stop(); return }
  if (busy.value || props.disabled || disposed) return
  requesting.value = true; error.value = ''; notice.value = ''; player.value?.pause()
  const current = ++generation
  try {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('当前浏览器不支持录音，请使用 HTTPS 或本机地址，并使用 Chrome / Edge。')
    const acquired = await navigator.mediaDevices.getUserMedia({ audio: true })
    if (disposed || current !== generation) { acquired.getTracks().forEach(track => track.stop()); return }
    stream = acquired
    const mime = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type))
    const activeRecorder = new MediaRecorder(stream, { audioBitsPerSecond: RECORDING_AUDIO_BITRATE, ...(mime ? { mimeType: mime } : {}) })
    recorder = activeRecorder
    const chunks = []; let bytes = 0, failed = false
    activeRecorder.ondataavailable = event => {
      if (disposed || current !== generation || failed) return
      bytes += event.data.size
      if (bytes > MAX_AUDIO_BYTES) {
        failed = true; error.value = '录音超过 25 MB，请缩短录音后重试。'
        if (activeRecorder.state === 'recording') activeRecorder.stop()
        clearTimers(); stopTracks(); recording.value = false
      } else if (event.data.size) chunks.push(event.data)
    }
    activeRecorder.onerror = () => {
      if (disposed || current !== generation) return
      failed = true; error.value = '录音中断，请重新录制。'
      if (activeRecorder.state === 'recording') activeRecorder.stop()
      clearTimers(); stopTracks(); recording.value = false
    }
    activeRecorder.onstop = () => {
      if (disposed || current !== generation) return
      clearTimers(); stopTracks(); recording.value = false
      if (failed) return
      blob = new Blob(chunks, { type: activeRecorder.mimeType || mime || 'audio/webm' })
      if (!blob.size) { error.value = '未录到音频，请重新录制。'; return }
      recordedUrl.value = URL.createObjectURL(blob)
      transcribe()
    }
    activeRecorder.start(1000)
    clearPreview(); blob = null; asrFailed.value = false
    requesting.value = false; recording.value = true; elapsedMs.value = 0
    const started = Date.now()
    ticker = setInterval(() => { elapsedMs.value = Date.now() - started }, 1000)
    timer = setTimeout(() => { if (activeRecorder.state === 'recording') activeRecorder.stop() }, MAX_RECORDING_MS)
  } catch (e) {
    if (disposed || current !== generation) return
    clearTimers(); stopTracks(); recording.value = false
    error.value = e.name === 'NotAllowedError' ? '麦克风权限被拒绝，请在浏览器中允许访问麦克风后重试。' : e.name === 'NotFoundError' ? '未检测到麦克风，请连接设备后重试。' : e.message
  } finally { if (current === generation) requesting.value = false }
}
onBeforeUnmount(() => {
  disposed = true; generation++; asrController?.abort(); clearTimers()
  if (recorder?.state === 'recording') recorder.stop()
  stopTracks(); clearPreview(); blob = null; emit('busy', false)
})
</script>

<style scoped>
.voice-input { margin: 16px 0 22px; font-size: 13px; color: #67785f; }
.voice-actions,.voice-preview { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.voice-actions > button { display: inline-flex; align-items: center; gap: 8px; }
.voice-actions span { line-height: 1.8; }
.voice-input p { margin: 12px 0; line-height: 1.8; overflow-wrap: anywhere; }
.voice-preview { margin-top: 14px; }
.voice-preview audio { width: 300px; max-width: 100%; height: 38px; }
.voice-error,.recording { color: #a53f35; }
.recording { background: #fff1eb; }
</style>
