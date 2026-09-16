export const API = import.meta.env?.VITE_API_BASE || ''
function responseError(data, status) {
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) return data.detail.map(e => `${e.loc?.join('.')}：${e.msg}`).join('；')
  return `请求失败 (${status})`
}
export async function request(path, options = {}) {
  const token = localStorage.getItem('mianmian-token')
  options.headers = { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  const response = await fetch(API + path, options)
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(responseError(data, response.status))
  }
  return response.json()
}
export async function requestBlob(path, options = {}) {
  const token = localStorage.getItem('mianmian-token')
  const response = await fetch(API + path, {...options, headers: {...(options.headers || {}), ...(token ? {Authorization: `Bearer ${token}`} : {})}})
  if (!response.ok) throw new Error(responseError(await response.json().catch(() => ({})), response.status))
  if (!response.headers.get('Content-Type')?.includes('application/pdf')) throw new Error('未收到有效 PDF，请重试')
  return response.blob()
}
export async function importQuestions(body, onProgress, signal) {
  const token = localStorage.getItem('mianmian-token')
  const response = await fetch(API + '/api/v1/teacher/question-bank/import?stream=true', {
    method: 'POST', body, signal, headers: token ? {Authorization: `Bearer ${token}`} : {},
  })
  if (!response.ok) throw new Error(responseError(await response.json().catch(() => ({})), response.status))
  const reader = response.body.getReader(), decoder = new TextDecoder()
  let buffer = '', draft
  function consume(line) {
    if (!line.trim()) return
    const event = JSON.parse(line)
    if (event.type === 'error') throw new Error(event.message)
    if (event.type === 'progress') onProgress(event)
    if (event.type === 'complete') draft = event.draft
  }
  try {
    while (true) {
      const {value, done} = await reader.read()
      buffer += decoder.decode(value, {stream: !done})
      const lines = buffer.split('\n'); buffer = lines.pop()
      lines.forEach(consume)
      if (done) break
    }
    consume(buffer)
    if (!draft) throw new Error('导入连接中断，未收到完整结果，请重新导入')
    return draft
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
export function wsUrl(id) {
  const url = new URL(API || location.origin, location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `/ws/interviews/${id}`
  const token = localStorage.getItem('mianmian-token')
  if (token) url.searchParams.set('token', token)
  return url.href
}
