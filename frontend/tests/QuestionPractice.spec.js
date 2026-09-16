// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import QuestionPractice from '../src/views/QuestionPractice.vue'
const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../src/api', () => ({ request }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: 'question' } }) }))
const context = () => ({ bookmark: { question: '如何评估 RAG？', job_track: 'AI 开发' }, total: 0, attempts: [], previous: { attempt_id: null, label: '原面试回答', answer: '看效果' }, in_progress: false })
let wrapper, recorder, track, getUserMedia
const button = text => wrapper.findAll('button').find(b => b.text() === text)
const asrCalls = () => request.mock.calls.filter(([path]) => path.endsWith('/asr'))
const submissions = () => request.mock.calls.filter(([path, options]) => path.endsWith('/practice') && options.method === 'POST')
async function open() { wrapper = mount(QuestionPractice, { global: { stubs: { RouterLink: true, LogoutButton: true } } }); await flushPromises() }
async function start() { await button('语音输入').trigger('click'); await flushPromises() }
async function stop() { await button('停止并转写').trigger('click'); await flushPromises() }
beforeEach(() => {
  request.mockReset(); request.mockImplementation(async path => path.endsWith('/asr') ? { text: '检索和生成分开评估。' } : context())
  track = { stop: vi.fn() }; getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [track] })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported() { return true }
    constructor() { recorder = this; this.mimeType = 'audio/webm'; this.state = 'inactive' }
    start() { this.state = 'recording' }
    stop() { this.state = 'inactive'; this.ondataavailable({ data: new Blob(['audio']) }); this.onstop() }
  })
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:recording')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
})
afterEach(() => { wrapper?.unmount(); wrapper = null; vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('appends transcription, allows editing and submits only on confirmation', async () => {
  await open(); await wrapper.find('textarea').setValue('我的思路'); await start()
  expect(button('提交并查看进步').attributes('disabled')).toBeDefined()
  await stop()
  expect(wrapper.find('textarea').element.value).toBe('我的思路\n检索和生成分开评估。')
  expect(track.stop).toHaveBeenCalled(); expect(asrCalls()[0][1].body.get('file').name).toBe('answer.webm')
  expect(submissions()).toHaveLength(0)
  await wrapper.find('textarea').setValue('编辑后的回答')
  request.mockRejectedValueOnce(new Error('稍后重试'))
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(JSON.parse(submissions()[0][1].body)).toMatchObject({ answer: '编辑后的回答', previous_attempt_id: null })
})
it('keeps audio on failure and retries without duplicating text', async () => {
  await open(); await wrapper.find('textarea').setValue('已有回答')
  request.mockRejectedValueOnce(new Error('ASR 暂忙')); await start(); await stop()
  expect(wrapper.text()).toContain('录音已保留'); expect(wrapper.find('audio').exists()).toBe(true)
  expect(wrapper.find('textarea').element.value).toBe('已有回答')
  await button('重试转写').trigger('click'); await flushPromises()
  expect(wrapper.find('textarea').element.value).toBe('已有回答\n检索和生成分开评估。')
  expect(button('重试转写')).toBeUndefined(); expect(asrCalls()).toHaveLength(2)
})
it('handles denied permission and cancels a late permission grant', async () => {
  await open(); getUserMedia.mockRejectedValueOnce(Object.assign(new Error(), { name: 'NotAllowedError' }))
  await start(); expect(wrapper.text()).toContain('麦克风权限被拒绝')
  let resolve; getUserMedia.mockImplementationOnce(() => new Promise(r => { resolve = r }))
  await start(); await button('取消').trigger('click'); resolve({ getTracks: () => [track] }); await flushPromises()
  expect(track.stop).toHaveBeenCalled(); expect(asrCalls()).toHaveLength(0)
  expect(button('语音输入').attributes('disabled')).toBeUndefined()
})
it('preserves long text and requires editing before submission', async () => {
  await open(); request.mockResolvedValueOnce({ text: '长'.repeat(6001) }); await start(); await stop()
  expect(wrapper.find('textarea').element.value).toHaveLength(6001); expect(wrapper.text()).toContain('全文已保留')
  expect(button('提交并查看进步').attributes('disabled')).toBeDefined()
  await wrapper.find('textarea').setValue('精简回答'); expect(button('提交并查看进步').attributes('disabled')).toBeUndefined()
})
it('continues past two minutes and automatically stops at ten minutes', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })
  await open(); await start(); await vi.advanceTimersByTimeAsync(120000)
  expect(recorder.state).toBe('recording'); expect(wrapper.text()).toContain('02:00')
  await vi.advanceTimersByTimeAsync(480000); await flushPromises()
  expect(recorder.state).toBe('inactive'); expect(asrCalls()).toHaveLength(1); expect(track.stop).toHaveBeenCalled()
})
it('releases microphone on navigation without uploading unfinished audio', async () => {
  await open(); await start(); wrapper.unmount(); wrapper = null; await flushPromises()
  expect(track.stop).toHaveBeenCalled(); expect(asrCalls()).toHaveLength(0)
})
it('aborts pending transcription and revokes its preview on navigation', async () => {
  await open(); let resolve; request.mockImplementationOnce(() => new Promise(r => { resolve = r }))
  await start(); await stop(); expect(button('提交并查看进步').attributes('disabled')).toBeDefined()
  const signal = asrCalls()[0][1].signal; wrapper.unmount(); wrapper = null
  expect(signal.aborted).toBe(true); resolve({ text: '迟到的结果' }); await flushPromises()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:recording'); expect(submissions()).toHaveLength(0)
})
it('rejects oversized and interrupted recordings without uploading', async () => {
  await open(); await start(); recorder.ondataavailable({ data: { size: 26 * 1024 * 1024 } }); await flushPromises()
  expect(wrapper.text()).toContain('录音超过 25 MB'); expect(asrCalls()).toHaveLength(0)
  await start(); recorder.onerror(); await flushPromises()
  expect(wrapper.text()).toContain('录音中断'); expect(asrCalls()).toHaveLength(0)
  expect(button('语音输入').attributes('disabled')).toBeUndefined()
})
