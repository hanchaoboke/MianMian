// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import EvaluationSheetDownload from '../src/components/EvaluationSheetDownload.vue'
import Report from '../src/views/Report.vue'
const { request, requestBlob }=vi.hoisted(()=>({request:vi.fn(),requestBlob:vi.fn()}))
vi.mock('../src/api',()=>({request,requestBlob}))
vi.mock('vue-router',()=>({useRoute:()=>({params:{id:'session'}})}))
let wrapper
beforeEach(()=>{
  vi.resetAllMocks()
  vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:pdf')
  vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>{})
  vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
})
afterEach(()=>{wrapper?.unmount();wrapper=null;vi.useRealTimers();vi.restoreAllMocks()})
it('automatically prepares and downloads the authenticated cached PDF on click',async()=>{
  request.mockResolvedValue({status:'ready'});requestBlob.mockResolvedValue(new Blob(['%PDF-1.7'],{type:'application/pdf'}))
  wrapper=mount(EvaluationSheetDownload,{props:{sessionId:'session'}});await flushPromises()
  expect(request).toHaveBeenCalledWith('/api/v1/interviews/session/evaluation-sheet',expect.objectContaining({method:'POST'}))
  expect(requestBlob).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('单页 A4')
  await wrapper.get('button').trigger('click');await flushPromises()
  expect(requestBlob).toHaveBeenCalledWith('/api/v1/interviews/session/evaluation-sheet.pdf',expect.any(Object))
  expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1)
  wrapper.unmount();wrapper=null
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:pdf')
})
it('polls an existing generation without sending another generation request',async()=>{
  vi.useFakeTimers()
  request.mockResolvedValueOnce({status:'generating'}).mockResolvedValueOnce({status:'ready'})
  wrapper=mount(EvaluationSheetDownload,{props:{sessionId:'session'}});await flushPromises()
  expect(wrapper.text()).toContain('正在填写')
  await vi.advanceTimersByTimeAsync(4000);await flushPromises()
  expect(request).toHaveBeenCalledTimes(2)
  expect(request.mock.calls[1][1].method).toBeUndefined()
  expect(wrapper.text()).toContain('下载评价表 PDF')
})
it('retries failures and keeps report readable during automatic generation',async()=>{
  request.mockImplementation(async path=>{
    if(path.endsWith('/report'))return {overall_score:80,dimensions:{},summary:'已完成',turns:[],interview_summary:{conclusion:'原诊断仍然可读',strengths:[],priorities:[],next_steps:[]}}
    throw new Error('模型暂忙')
  })
  wrapper=mount(Report,{global:{stubs:{RouterLink:true}}});await flushPromises()
  expect(wrapper.text()).toContain('原诊断仍然可读');expect(wrapper.text()).toContain('原诊断仍可查看')
  request.mockResolvedValue({status:'ready'})
  await wrapper.get('.evaluation-export button').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('下载评价表 PDF')
})
it('does not download an HTML or failed response and leaves the download retry available',async()=>{
  request.mockResolvedValue({status:'ready'});requestBlob.mockRejectedValue(new Error('未收到有效 PDF'))
  wrapper=mount(EvaluationSheetDownload,{props:{sessionId:'session'}});await flushPromises()
  await wrapper.get('button').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('下载失败');expect(URL.createObjectURL).not.toHaveBeenCalled()
  expect(wrapper.get('button').text()).toBe('下载评价表 PDF')
})
it('discards old report responses and aborts outstanding requests on unmount',async()=>{
  let resolve
  request.mockImplementationOnce(()=>new Promise(r=>{resolve=r})).mockResolvedValue({status:'ready'})
  wrapper=mount(EvaluationSheetDownload,{props:{sessionId:'old'}})
  const oldSignal=request.mock.calls[0][1].signal
  await wrapper.setProps({sessionId:'new'});await flushPromises()
  resolve({status:'generating'});await flushPromises()
  expect(oldSignal.aborted).toBe(true);expect(wrapper.text()).toContain('下载评价表 PDF')
  const newSignal=request.mock.calls[1][1].signal
  wrapper.unmount();wrapper=null;expect(newSignal.aborted).toBe(true)
})
it('offers regeneration when a teacher changed the template after the report was opened',async()=>{
  request.mockResolvedValue({status:'ready'})
  requestBlob.mockRejectedValue(new Error('评价表尚未生成或教师已更新模板，请刷新诊断页重新生成'))
  wrapper=mount(EvaluationSheetDownload,{props:{sessionId:'session'}});await flushPromises()
  await wrapper.get('button').trigger('click');await flushPromises()
  expect(wrapper.get('button').text()).toBe('重新生成评价表')
  await wrapper.get('button').trigger('click');await flushPromises()
  expect(request).toHaveBeenCalledTimes(2)
  expect(wrapper.get('button').text()).toBe('下载评价表 PDF')
})
