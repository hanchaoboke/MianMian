// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Report from '../src/views/Report.vue'
import LogoutButton from '../src/components/LogoutButton.vue'
import App from '../src/App.vue'
import { historyItems, clearHistory } from '../src/studentHistory'
const { request } = vi.hoisted(() => ({request:vi.fn()}))
vi.mock('../src/api', () => ({request}))
vi.mock('../src/components/EvaluationSheetDownload.vue', () => ({default:{template:'<div />'}}))
let wrapper, router
const summary = {conclusion:'能建立评估思路。',strengths:['指标意识清晰。'],priorities:['补充业务验收标准。'],next_steps:['写一份业务验收表。']}
const report = {overall_score:75,dimensions:{},summary:'完成一轮',turns:[{turn:1,score:75,question:'怎么评估？',answer:'真实问题集',feedback:'完善指标'}]}
beforeEach(async () => {
  vi.clearAllMocks();localStorage.clear();clearHistory()
  router = createRouter({history:createMemoryHistory(),routes:[{path:'/report/:id',component:{template:'<div />'}},{path:'/:pathMatch(.*)*',component:{template:'<div />'}}]})
  await router.push('/report/session');await router.isReady()
})
afterEach(() => {wrapper?.unmount();localStorage.clear();clearHistory()})

it.each([['/','/login'],['/teacher/classes','/teacher/login']])('logs out %s to its own login',async (path, target) => {
  await router.push(path)
  localStorage.setItem('mianmian-token','token');localStorage.setItem('mianmian-user','{}');historyItems.value=[{session_id:'old'}]
  request.mockResolvedValue({ok:true})
  wrapper=mount(LogoutButton,{global:{plugins:[router]}})
  await wrapper.find('button').trigger('click');await flushPromises()
  expect(request).toHaveBeenCalledWith('/api/v1/auth/logout',expect.objectContaining({method:'POST'}))
  expect(localStorage.getItem('mianmian-token')).toBeNull();expect(localStorage.getItem('mianmian-user')).toBeNull()
  expect(historyItems.value).toEqual([]);expect(router.currentRoute.value.path).toBe(target)
})

it('clears local login even if logout cannot reach the server',async () => {
  localStorage.setItem('mianmian-token','token');request.mockRejectedValue(new Error('offline'))
  wrapper=mount(LogoutButton,{global:{plugins:[router]}})
  await wrapper.find('button').trigger('click');await flushPromises()
  expect(localStorage.getItem('mianmian-token')).toBeNull();expect(router.currentRoute.value.path).toBe('/login')
})

it('shows cached summary before per-question review without a model request',async () => {
  request.mockResolvedValue({...report,interview_summary:summary})
  wrapper=mount(Report,{global:{plugins:[router]}});await flushPromises()
  expect(request).toHaveBeenCalledTimes(1)
  expect(wrapper.findAll('.recommendations h3').map(h=>h.text())).toEqual(['面试总结','逐题复盘'])
  expect(wrapper.text()).toContain(summary.strengths[0]);expect(wrapper.text()).toContain(summary.next_steps[0])
})

it('keeps question review usable on summary failure and retries successfully',async () => {
  request.mockResolvedValueOnce(report).mockRejectedValueOnce(new Error('模型忙')).mockResolvedValueOnce(summary)
  wrapper=mount(Report,{global:{plugins:[router]}});await flushPromises()
  expect(wrapper.text()).toContain('逐题复盘仍可查看');expect(wrapper.text()).toContain('真实问题集')
  await wrapper.find('.interview-summary button').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain(summary.conclusion);expect(wrapper.find('.interview-summary .error').exists()).toBe(false)
})

it('shows the business brief and evaluates proposal structure instead of past project storytelling',async () => {
  request.mockResolvedValue({...report,interview_summary:summary,interview_mode:'BUSINESS_SCENARIO',business_scenario:{requirement:'公司需要 AI 客服接入现有工单系统。',constraints:'六周上线',success_criteria:'答案可追溯'}})
  wrapper=mount(Report,{global:{plugins:[router]}});await flushPromises()
  expect(wrapper.find('.business-brief').text()).toContain('六周上线')
  expect(wrapper.find('.dimensions').text()).toContain('方案表达')
  expect(wrapper.find('.dimensions').text()).not.toContain('STAR 表达')
})

it('shows exactly one diagnosis heading in the complete student page',async () => {
  request.mockImplementation(async path=>path.includes('/student/interviews') ? {items:[],dates:{}} : {...report,interview_summary:summary})
  router.addRoute({path:'/report/:id',component:Report})
  await router.replace('/report/heading-check')
  wrapper=mount(App,{global:{plugins:[router]}});await flushPromises()
  expect(wrapper.findAll('h1,h2').filter(h=>h.text()==='面试诊断')).toHaveLength(1)
  expect(wrapper.find('h1').text()).toBe('面试诊断')
})

it('expands a long answer without hiding its feedback or changing its contents',async () => {
  const answer='这是学生的完整回答。'.repeat(55)
  request.mockResolvedValue({...report,interview_summary:summary,turns:[{...report.turns[0],answer,feedback:'工程深度：需要补充验证过程。改进建议：1）准备数据；2）对比结果。'}]})
  wrapper=mount(Report,{global:{plugins:[router]}});await flushPromises()
  expect(wrapper.find('.answer-pane .transcript').text()).toBe(answer.slice(0,360)+'…')
  expect(wrapper.find('.feedback-pane').text()).toContain('需要补充验证过程')
  expect(wrapper.findAll('.feedback-pane li')).toHaveLength(2)
  await wrapper.find('.answer-toggle').trigger('click')
  expect(wrapper.find('.answer-pane .transcript').text()).toBe(answer)
  expect(wrapper.find('.answer-toggle').attributes('aria-expanded')).toBe('true')
  await wrapper.find('.answer-toggle').trigger('click')
  expect(wrapper.find('.answer-toggle').attributes('aria-expanded')).toBe('false')
})
