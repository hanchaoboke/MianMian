// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Bookmarks from '../src/views/Bookmarks.vue'
import Report from '../src/views/Report.vue'
import App from '../src/App.vue'

const { request } = vi.hoisted(()=>({request:vi.fn()}))
vi.mock('../src/api',()=>({request}))
vi.mock('../src/components/EvaluationSheetDownload.vue', () => ({default:{template:'<div />'}}))
let wrapper,router
const review={knowledge_points:['检索召回率','生成忠实度'],spoken_answer:'我会先收集真实业务问题，把检索和生成分开评估。'}
const item={id:'marked',session_id:'session',turn:1,question:'怎样评估 RAG？',job_track:'AI 开发',created_at:'2026-09-15T02:00:00Z',interview_started_at:'2026-09-14T02:00:00Z',status:'ready',review}
const report={overall_score:70,dimensions:{},summary:'完成一轮',turns:[{turn:1,score:70,question:item.question,answer:'先看结果',feedback:'需完善评测'}],interview_summary:{conclusion:'需完善评测',strengths:[],priorities:['完善评测'],next_steps:['建立评测集']}}
function list(items=[item],total=items.length,page=1){return {items:structuredClone(items),total,page,page_size:10}}
async function render(component,path='/bookmarks') {
  await router.push(path);await router.isReady()
  wrapper=mount(component,{global:{plugins:[router]}});await flushPromises()
}
beforeEach(()=>{
  vi.resetAllMocks();localStorage.clear()
  router=createRouter({history:createMemoryHistory(),routes:[{path:'/:pathMatch(.*)*',component:{template:'<div />'}},{path:'/report/:id',component:{template:'<div />'}}]})
})
afterEach(()=>{wrapper?.unmount();vi.useRealTimers();localStorage.clear()})

it('marks immediately, shows generation progress, and can unmark',async()=>{
  let resolveReview
  request.mockResolvedValueOnce(structuredClone(report)).mockResolvedValueOnce({...item,status:'pending',review:null})
    .mockImplementationOnce(()=>new Promise(resolve=>{resolveReview=resolve})).mockResolvedValueOnce({ok:true})
  await render(Report,'/report/session')
  await wrapper.get('.bookmark-button').trigger('click');await flushPromises()
  expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({session_id:'session',turn:1})
  expect(wrapper.get('.bookmark-button').attributes('aria-pressed')).toBe('true')
  expect(wrapper.get('.bookmark-button').attributes('disabled')).toBeDefined()
  expect(wrapper.text()).toContain('题目已保存')
  resolveReview(item);await flushPromises()
  expect(wrapper.get('.bookmark-button').attributes('disabled')).toBeUndefined()
  await wrapper.get('.bookmark-button').trigger('click');await flushPromises()
  expect(request).toHaveBeenLastCalledWith('/api/v1/student/bookmarks/marked',{method:'DELETE'})
  expect(wrapper.get('.bookmark-button').attributes('aria-pressed')).toBe('false')
})

it('keeps a successful mark when guide generation fails',async()=>{
  request.mockResolvedValueOnce(structuredClone(report)).mockResolvedValueOnce({...item,status:'pending',review:null}).mockRejectedValueOnce(new Error('模型暂忙'))
  await render(Report,'/report/session')
  await wrapper.get('.bookmark-button').trigger('click');await flushPromises()
  expect(wrapper.get('.bookmark-button').attributes('aria-pressed')).toBe('true')
  expect(wrapper.get('[role="alert"]').text()).toContain('题目已标记，复习内容暂未生成')
  expect(wrapper.find('a[href="/bookmarks"]').exists()).toBe(true)
})

it('shows report marks saved on the server after refresh',async()=>{
  request.mockResolvedValueOnce({...structuredClone(report),turns:[{...report.turns[0],bookmark_id:item.id}]})
  await render(Report,'/report/session')
  expect(wrapper.get('.bookmark-button').attributes('aria-pressed')).toBe('true')
  expect(request).toHaveBeenCalledTimes(1)
})

it('displays question, knowledge, spoken answer and the source report without regenerating',async()=>{
  request.mockResolvedValueOnce(list())
  await render(Bookmarks)
  expect(wrapper.text()).toContain(item.question)
  expect(wrapper.text()).toContain(review.knowledge_points[0])
  expect(wrapper.text()).toContain(review.spoken_answer)
  expect(wrapper.get('footer a').attributes('href')).toBe('/report/session')
  expect(request).toHaveBeenCalledTimes(1)
})

it('shows the empty state and recovers a list network failure',async()=>{
  request.mockRejectedValueOnce(new Error('网络中断')).mockResolvedValueOnce(list([]))
  await render(Bookmarks)
  expect(wrapper.get('[role="alert"]').text()).toContain('网络中断')
  await wrapper.get('[role="alert"] button').trigger('click');await flushPromises()
  expect(wrapper.find('.review-empty').exists()).toBe(true)
  expect(wrapper.find('.review-card').exists()).toBe(false)
})

it('supports generation retry and preserves the question',async()=>{
  request.mockResolvedValueOnce(list([{...item,status:'pending',review:null}]))
    .mockRejectedValueOnce(new Error('模型暂忙')).mockResolvedValueOnce(item)
  await render(Bookmarks)
  expect(wrapper.text()).toContain(item.question)
  expect(wrapper.text()).toContain('模型暂忙')
  expect(request).toHaveBeenCalledTimes(2)
  await wrapper.get('.review-pending button').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain(review.spoken_answer)
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
})

it('polls a generation started in a report tab and stops polling after leaving',async()=>{
  vi.useFakeTimers()
  request.mockResolvedValueOnce(list([{...item,status:'generating',review:null}])).mockResolvedValueOnce(list())
  await render(Bookmarks)
  expect(wrapper.text()).toContain('正在整理这道题')
  await vi.advanceTimersByTimeAsync(4000);await flushPromises()
  expect(wrapper.text()).toContain(review.spoken_answer)
  expect(request).toHaveBeenCalledTimes(2)
  wrapper.unmount();wrapper=null
  await vi.advanceTimersByTimeAsync(10000)
  expect(request).toHaveBeenCalledTimes(2)
})

it('returns to the preceding page when its last item is removed',async()=>{
  request.mockResolvedValueOnce(list([item],11,1)).mockResolvedValueOnce(list([item],11,2))
    .mockResolvedValueOnce({ok:true}).mockResolvedValueOnce(list([],10,2)).mockResolvedValueOnce(list([item],10,1))
  await render(Bookmarks)
  await wrapper.get('.pagination button:last-child').trigger('click');await flushPromises()
  expect(request).toHaveBeenLastCalledWith('/api/v1/student/bookmarks?page=2')
  await wrapper.get('.remove-bookmark').trigger('click');await flushPromises()
  expect(request).toHaveBeenLastCalledWith('/api/v1/student/bookmarks?page=1')
  expect(wrapper.find('.pagination').exists()).toBe(false)
})

it('puts review navigation after the student calendar and hides both on teacher pages',async()=>{
  request.mockResolvedValue({items:[],dates:{}})
  await render(App,'/')
  const calendar=wrapper.get('.sidebar-calendar').element
  const navigation=wrapper.get('.bookmark-nav').element
  expect(calendar.nextElementSibling).toBe(navigation)
  expect(wrapper.get('.bookmark-nav a').attributes('href')).toBe('/bookmarks')
  await router.push('/bookmarks');await flushPromises()
  expect(wrapper.get('.bookmark-nav a').classes()).toContain('active')
  expect(wrapper.get('[aria-label="学生功能导航"] a').classes()).not.toContain('active')
  await router.push('/teacher');await flushPromises()
  expect(wrapper.find('.bookmark-nav').exists()).toBe(false)
  expect(wrapper.find('.sidebar-calendar').exists()).toBe(false)
})
