import { ref } from 'vue'
import { request } from './api'
export const historyItems = ref([])
export const historyDates = ref({})
export const historyLoading = ref(false)
export const historyError = ref('')
let version = 0
export async function refreshHistory() {
  const current = ++version
  historyLoading.value = true; historyError.value = ''; historyItems.value = []; historyDates.value = {}
  try {
    const data = await request('/api/v1/student/interviews')
    if (current !== version) return
    historyItems.value = data.items; historyDates.value = data.dates
  } catch (e) { if (current === version) historyError.value = e.message }
  finally { if (current === version) historyLoading.value = false }
}
export function clearHistory() { version++; historyItems.value = []; historyDates.value = {}; historyError.value = ''; historyLoading.value = false }
export function shanghaiDate(value = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(value)
  return ['year','month','day'].map(type => parts.find(p => p.type === type).value).join('-')
}
