<template>
  <div class="evaluation-export">
    <button v-if="status === 'ready'" class="secondary" :disabled="downloading" @click="download"><Download :size="16" />{{ downloading ? '正在下载…' : '下载评价表 PDF' }}</button>
    <button v-else-if="error" class="secondary" @click="prepare"><RefreshCw :size="16" />重新生成评价表</button>
    <span v-else class="export-status" role="status"><LoaderCircle :size="16" class="spin" />正在填写评价表…</span>
    <span v-if="status === 'ready'" class="export-note">已填好 · 仅第一页</span>
    <p v-if="error" class="export-error" role="alert">{{ error }}</p>
  </div>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Download, LoaderCircle, RefreshCw } from 'lucide-vue-next'
import { request, requestBlob } from '../api'
const props = defineProps({ sessionId: {type:String, required:true} })
const status=ref('pending'), error=ref(''), downloading=ref(false)
let version=0, controller, timer
const urls=new Set(), revokeTimers=new Set()
const path=()=>`/api/v1/interviews/${encodeURIComponent(props.sessionId)}/evaluation-sheet`
async function check(current) {
  try {
    const data=await request(path(), {signal:controller.signal})
    if(current!==version)return
    status.value=data.status
    if(data.status==='ready')return
    if(data.status==='generating')timer=setTimeout(()=>check(current),4000)
    else error.value=data.error || '生成已中断，可以重新生成。'
  } catch(e){if(current===version)error.value=e.message}
}
async function prepare() {
  clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++version
  error.value='';status.value='generating'
  try {
    const data=await request(path(),{method:'POST',signal:controller.signal})
    if(current!==version)return
    status.value=data.status
    if(data.status==='generating')timer=setTimeout(()=>check(current),4000)
    else if(data.status!=='ready')error.value=data.error || '评价表暂未生成，请重试。'
  } catch(e){if(current===version)error.value=`${e.message}。原诊断仍可查看。`}
}
async function download() {
  if(downloading.value)return
  downloading.value=true;error.value='';const current=version
  try {
    const blob=await requestBlob(path()+'.pdf',{signal:controller.signal})
    if(current!==version)return
    const url=URL.createObjectURL(blob);urls.add(url)
    const link=document.createElement('a');link.href=url;link.download=`面试评价表_${props.sessionId.replace(/[^\w-]/g,'_')}.pdf`
    document.body.appendChild(link);link.click();link.remove()
    const timeout=setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);revokeTimers.delete(timeout)},60000)
    revokeTimers.add(timeout)
  } catch(e){if(current===version)error.value=`下载失败：${e.message}。请再次点击下载。`}
  finally{if(current===version)downloading.value=false}
}
watch(()=>props.sessionId,()=>{downloading.value=false;prepare()},{immediate:true})
onBeforeUnmount(()=>{version++;controller?.abort();clearTimeout(timer);for(const t of revokeTimers)clearTimeout(t);for(const url of urls)URL.revokeObjectURL(url)})
</script>
<style scoped>
.evaluation-export { display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
.evaluation-export button,.export-status { display:inline-flex; align-items:center; gap:8px; }
.export-status,.export-note { color:#6a7a6c; font-size:13px; }
.export-error { flex-basis:100%; font-size:13px; line-height:1.7; color:#a04436; overflow-wrap:anywhere; }
.spin { animation:export-spin 1s linear infinite; }
@keyframes export-spin { to { transform:rotate(360deg); } }
@media(prefers-reduced-motion:reduce){ .spin { animation:none; } }
</style>
