// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Interview from '../src/views/Interview.vue'

const { request, replace } = vi.hoisted(() => ({request:vi.fn(), replace:vi.fn()}))
vi.mock('../src/api', () => ({request, API:'', wsUrl:() => 'ws://test/interview'}))
vi.mock('vue-router', () => ({useRoute:() => ({params:{id:'test'}}), useRouter:() => ({replace})}))
const session = () => ({session_id:'test', status:'IN_PROGRESS', job_track:'AI 开发', style:'GUIDING', history:[], turn:0, target_question_count:2, started_at:new Date().toISOString(), question:'介绍 RAG 项目？'})
let wrapper, socket, recorder, track, getUserMedia
const button = name => wrapper.findAll('button').find(b => b.text() === name)
async function open() {
  wrapper = mount(Interview, {global:{stubs:{RouterLink:true}}})
  await flushPromises(); socket.onopen(); await flushPromises()
}
beforeEach(() => {
  vi.clearAllMocks()
  request.mockImplementation(async path => path.endsWith('/asr') ? {text:'使用混合检索。'} : session())
  track = {stop:vi.fn()}; getUserMedia = vi.fn().mockResolvedValue({getTracks:() => [track]})
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia}})
  vi.stubGlobal('WebSocket', class {
    static OPEN = 1
    constructor(){socket=this;this.readyState=1;this.send=vi.fn();this.close=vi.fn()}
  })
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported(){return true}
    constructor(){recorder=this;this.mimeType='audio/webm';this.state='inactive'}
    start(){this.state='recording'}
    stop(){this.state='inactive';this.ondataavailable({data:new Blob(['recorded audio'])});this.onstop()}
  })
  vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:test')
  vi.spyOn(URL,'revokeObjectURL').mockImplementation(() => {})
  vi.spyOn(window,'scrollTo').mockImplementation(() => {})
})
afterEach(() => {wrapper?.unmount();vi.useRealTimers();vi.restoreAllMocks();vi.unstubAllGlobals()})

describe('Interview room', () => {
  it('records, transcribes and sends only after student confirmation', async () => {
    await open()
    await button('语音输入').trigger('click'); await flushPromises()
    expect(button('停止并转写')).toBeDefined()
    expect(button('发送回答').attributes('disabled')).toBeDefined()
    await button('停止并转写').trigger('click'); await flushPromises()
    expect(wrapper.find('textarea').element.value).toBe('使用混合检索。')
    expect(track.stop).toHaveBeenCalled()
    expect(socket.send).not.toHaveBeenCalled()
    await wrapper.find('form').trigger('submit')
    expect(JSON.parse(socket.send.mock.calls[0][0])).toMatchObject({event:'ANSWER',text:'使用混合检索。'})
  })
  it('retains recorded audio on ASR failure and retries without re-recording', async () => {
    await open()
    request.mockRejectedValueOnce(new Error('ASR 服务忙'))
    await button('语音输入').trigger('click'); await flushPromises()
    await button('停止并转写').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('录音已保留')
    expect(button('重试转写')).toBeDefined()
    await button('重试转写').trigger('click'); await flushPromises()
    expect(wrapper.find('textarea').element.value).toBe('使用混合检索。')
  })
  it('handles denied permission and discards a late grant after cancellation', async () => {
    await open()
    getUserMedia.mockRejectedValueOnce(Object.assign(new Error(),{name:'NotAllowedError'}))
    await button('语音输入').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('麦克风权限被拒绝')
    let resolve
    getUserMedia.mockImplementationOnce(() => new Promise(r => {resolve=r}))
    await button('语音输入').trigger('click'); await flushPromises()
    await button('取消').trigger('click')
    resolve({getTracks:() => [track]}); await flushPromises()
    expect(track.stop).toHaveBeenCalled()
    expect(button('语音输入').attributes('disabled')).toBeUndefined()
  })
  it('keeps long transcripts intact and stops submission until edited', async () => {
    await open()
    request.mockResolvedValueOnce({text:'长'.repeat(6001)})
    await button('语音输入').trigger('click'); await flushPromises()
    await button('停止并转写').trigger('click'); await flushPromises()
    expect(wrapper.find('textarea').element.value.length).toBe(6001)
    expect(button('发送回答').attributes('disabled')).toBeDefined()
  })
  it('continues past two minutes and automatically transcribes at ten minutes', async () => {
    vi.useFakeTimers({toFake:['setTimeout','clearTimeout']})
    await open()
    await button('语音输入').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('最长 10:00')
    await vi.advanceTimersByTimeAsync(120000)
    expect(recorder.state).toBe('recording')
    expect(request.mock.calls.filter(([path])=>path.endsWith('/asr'))).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(480000); await flushPromises()
    expect(recorder.state).toBe('inactive')
    expect(track.stop).toHaveBeenCalled()
    expect(request.mock.calls.filter(([path])=>path.endsWith('/asr'))).toHaveLength(1)
    expect(wrapper.find('textarea').element.value).toBe('使用混合检索。')
  })
  it('allows a long spoken answer within the new limit to be submitted intact', async () => {
    await open()
    request.mockResolvedValueOnce({text:'长'.repeat(6000)})
    await button('语音输入').trigger('click'); await flushPromises()
    await button('停止并转写').trigger('click'); await flushPromises()
    expect(wrapper.find('textarea').element.value.length).toBe(6000)
    expect(button('发送回答').attributes('disabled')).toBeUndefined()
    await wrapper.find('form').trigger('submit')
    expect(JSON.parse(socket.send.mock.calls[0][0]).text).toHaveLength(6000)
  })
  it('shows question history without assessment and opens report only at completion', async () => {
    await open()
    socket.onmessage({data:JSON.stringify({type:'SESSION_STATE',payload:{...session(),turn:1,question:'如何评估？',history:[{turn:1,question:'介绍项目',answer:'检索方案',score:30,feedback:'不应显示的反馈'}]}})})
    await flushPromises()
    expect(wrapper.text()).not.toContain('不应显示的反馈')
    expect(replace).not.toHaveBeenCalled()
    socket.onmessage({data:JSON.stringify({type:'SESSION_STATE',payload:{...session(),turn:2,status:'COMPLETED'}})})
    expect(replace).toHaveBeenCalledWith('/report/test')
  })
  it('releases microphone on leaving without uploading an unfinished recording', async () => {
    await open()
    await button('语音输入').trigger('click'); await flushPromises()
    wrapper.unmount(); wrapper = null; await flushPromises()
    expect(track.stop).toHaveBeenCalled()
    expect(request.mock.calls.filter(([path])=>path.endsWith('/asr'))).toHaveLength(0)
  })
})
