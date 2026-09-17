// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Workspace from '../src/views/Workspace.vue'
import InterviewCalendar from '../src/components/InterviewCalendar.vue'
import { clearHistory, refreshHistory } from '../src/studentHistory'

const { request } = vi.hoisted(() => ({request: vi.fn()}))
vi.mock('../src/api', () => ({request}))
let wrapper, router
beforeEach(async () => {
  clearHistory(); vi.clearAllMocks()
  request.mockImplementation(async path => path === '/api/v1/student/interviews' ? {
    items: [
      {session_id:'latest', date:'2026-09-14', started_at:'2026-09-14T10:00:00Z', job_track:'最新一场', style:'ALL_ROUND', turn:3, target_question_count:3, status:'COMPLETED', has_report:true},
      {session_id:'older', date:'2026-08-31', started_at:'2026-08-31T10:00:00Z', job_track:'上一场', style:'CREATIVE', turn:1, target_question_count:3, status:'IN_PROGRESS', has_report:false},
    ], dates:{'2026-09-14':1, '2026-08-31':1},
  } : path === '/api/v1/interviews' ? {session_id:'created'} : {items:[]})
  router = createRouter({history:createMemoryHistory(), routes:[{path:'/:pathMatch(.*)*', component:{template:'<div />'}}]})
  await router.push('/?date=2026-09-14'); await router.isReady(); await refreshHistory()
  wrapper = mount({components:{Workspace,InterviewCalendar},template:'<InterviewCalendar /><Workspace />'}, {global:{plugins:[router]}})
  await flushPromises()
})
afterEach(() => {wrapper.unmount(); clearHistory()})

it('filters by calendar date, restores all records and links to the original report', async () => {
  expect(wrapper.find('[aria-label="2026-09-14，1 场面试"]').classes()).toContain('has-interview')
  expect(wrapper.findAll('.history-entry')).toHaveLength(1)
  expect(wrapper.find('.history-link').attributes('href')).toBe('/report/latest')
  await wrapper.find('[aria-label="2026-09-15，0 场面试"]').trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('当天还没有模拟面试')
  await wrapper.find('.calendar-all').trigger('click'); await flushPromises()
  expect(wrapper.findAll('.history-entry').map(row => row.find('h4').text())).toEqual(['最新一场', '上一场'])
  expect(wrapper.findAll('.history-link')[1].attributes('href')).toBe('/interview/older')
  expect(wrapper.text()).not.toContain('教师题库管理')
  expect(wrapper.text()).not.toContain('查看本次报告')
})

it('navigates months and shows marked dates from previous months', async () => {
  await wrapper.find('[aria-label="上个月"]').trigger('click')
  expect(wrapper.find('[aria-label="2026-08-31，1 场面试"]').classes()).toContain('has-interview')
  await wrapper.find('[aria-label="2026-08-31，1 场面试"]').trigger('click'); await flushPromises()
  expect(wrapper.findAll('.history-entry')).toHaveLength(1)
  expect(wrapper.find('.history-info h4').text()).toBe('上一场')
})

it.each(['CREATIVE', 'ALL_ROUND'])('starts the selected %s style', async style => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  const selects = wrapper.findAll('select')
  expect(selects[0].findAll('option')).toHaveLength(5)
  await selects[0].setValue(style)
  await wrapper.find('textarea').setValue('我做过企业知识库问答项目。')
  await wrapper.find('.modal-actions .primary').trigger('click'); await flushPromises()
  const call = request.mock.calls.find(([path]) => path === '/api/v1/interviews')
  expect(JSON.parse(call[1].body).interviewer_style).toBe(style)
  expect(router.currentRoute.value.path).toBe('/interview/created')
})

it('selects multiple job tracks instead of individual teacher questions', async () => {
  wrapper.unmount()
  request.mockResolvedValue({items:[{job_track:'AI 开发',question_count:41},{job_track:'Python 后端',question_count:12}]})
  wrapper = mount(Workspace,{global:{plugins:[router]}}); await flushPromises()
  await wrapper.find('.hero-actions .secondary').trigger('click')
  const choices = wrapper.findAll('.question-selection input')
  expect(choices).toHaveLength(2)
  await choices[0].setValue(true); await choices[1].setValue(true)
  expect(wrapper.text()).toContain('已选 2 个岗位题库')
  await wrapper.find('textarea').setValue('企业知识库项目')
  request.mockResolvedValueOnce({session_id:'track-session'})
  await wrapper.find('.modal-actions .primary').trigger('click'); await flushPromises()
  const payload = JSON.parse(request.mock.calls.find(([path]) => path === '/api/v1/interviews')[1].body)
  expect(payload.knowledge_tracks).toEqual(['AI 开发','Python 后端'])
  expect(payload.question_ids).toBeUndefined()
})

it.each([[1, '非常口语化'], [5, '严谨专业']])('saves expression level %s and sends it when starting', async (level, label) => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  expect(wrapper.find('input[type="range"]').element.value).toBe('3')
  await wrapper.find('input[type="range"]').setValue(String(level))
  expect(wrapper.find('.expression-heading output').text()).toBe(label)
  expect(wrapper.find('input[type="range"]').attributes('aria-valuetext')).toBe(label)
  await wrapper.find('.modal-actions .secondary').trigger('click')
  await wrapper.find('.hero-actions .secondary').trigger('click')
  expect(wrapper.find('input[type="range"]').element.value).toBe(String(level))
  await wrapper.find('textarea').setValue('我负责企业知识库项目的评测。')
  await wrapper.find('.modal-actions .primary').trigger('click'); await flushPromises()
  const payload = JSON.parse(request.mock.calls.find(([path]) => path === '/api/v1/interviews')[1].body)
  expect(payload.question_expression).toBe(level)
  expect(payload.experience_years).toBe('1-3')
})

async function uploadFile(selector, name) {
  const input = wrapper.find(selector)
  Object.defineProperty(input.element, 'files', {value: [new File(['test'], name)], configurable: true})
  await input.trigger('change')
}

it('shows resume processing, completion, preserves it on replacement failure, and allows removal', async () => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  let resolveUpload
  request.mockReturnValueOnce(new Promise(resolve => { resolveUpload = resolve }))
  await uploadFile('.resume-file-input', '我的简历.pdf')
  expect(wrapper.find('.resume-section').text()).toContain('正在上传并解析简历')
  expect(wrapper.find('.knowledge-section').text()).not.toContain('正在上传')
  expect(wrapper.find('.modal-actions .primary').attributes('disabled')).toBeDefined()
  resolveUpload({resume_id: 'resume-1', filename: '我的简历.pdf', text: '企业问答项目经历'})
  await flushPromises()
  expect(wrapper.find('.resume-section').text()).toContain('已上传')
  expect(wrapper.find('.resume-file').text()).toContain('我的简历.pdf')
  expect(wrapper.find('.resume-file').text()).toContain('本次面试使用')
  expect(wrapper.find('textarea').exists()).toBe(false)
  request.mockRejectedValueOnce(new Error('文件解析失败'))
  await uploadFile('.resume-file-input', '新简历.pdf'); await flushPromises()
  expect(wrapper.find('.resume-section [role="alert"]').text()).toContain('文件解析失败')
  expect(wrapper.find('.resume-file').text()).toContain('我的简历.pdf')
  await wrapper.find('[aria-label="移除简历"]').trigger('click')
  expect(wrapper.find('.resume-section').text()).toContain('尚未上传简历')
  expect(wrapper.find('textarea').exists()).toBe(true)
})

it('labels knowledge as optional, tracks files and selections, and removes only the selected file questions', async () => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  expect(wrapper.find('.optional-label').text()).toBe('可选')
  expect(wrapper.find('.knowledge-section').text()).toContain('不上传也可以开始面试')
  for (const id of ['first', 'second']) {
    request.mockResolvedValueOnce({knowledge_id:id, filename:`${id}.md`, questions:[{question:`${id}的问题`, answer:''}]})
    await uploadFile('.knowledge-file-input', `${id}.md`); await flushPromises()
  }
  expect(wrapper.findAll('.knowledge-file')).toHaveLength(2)
  expect(wrapper.find('.knowledge-footer').text()).toContain('尚未选题')
  const choices = wrapper.findAll('.temporary-questions input')
  await choices[0].setValue(true); await choices[1].setValue(true)
  expect(wrapper.find('.knowledge-footer').text()).toContain('本次已选 2 道')
  await wrapper.find('[aria-label="移除知识库 first.md"]').trigger('click')
  expect(wrapper.findAll('.knowledge-file')).toHaveLength(1)
  expect(wrapper.find('.knowledge-file').text()).toContain('second.md')
  expect(wrapper.find('.knowledge-footer').text()).toContain('本次已选 1 道')
  await wrapper.find('textarea').setValue('项目经历')
  await wrapper.find('.modal-actions .primary').trigger('click'); await flushPromises()
  const payload = JSON.parse(request.mock.calls.find(([path]) => path === '/api/v1/interviews')[1].body)
  expect(payload.temporary_questions.map(q => q.question)).toEqual(['second的问题'])
})

it('keeps knowledge upload errors local and does not mark the failed file as uploaded', async () => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  request.mockRejectedValueOnce(new Error('提取题目失败'))
  await uploadFile('.knowledge-file-input', '题库.docx'); await flushPromises()
  expect(wrapper.find('.knowledge-section [role="alert"]').text()).toContain('提取题目失败')
  expect(wrapper.find('.knowledge-file').exists()).toBe(false)
  expect(wrapper.find('.knowledge-section').text()).toContain('未添加')
  expect(wrapper.find('.resume-section [role="alert"]').exists()).toBe(false)
})

const modeButton = name => wrapper.findAll('.mode-options button').find(button => button.text().includes(name))
it('starts business interviews without a resume and sends the structured scenario', async () => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  await modeButton('企业业务').trigger('click')
  expect(wrapper.find('.resume-section').exists()).toBe(false)
  expect(wrapper.find('.business-section').text()).toContain('无需简历')
  const fields = wrapper.findAll('.business-section textarea')
  await fields[0].setValue('公司希望用 AI 处理商品咨询，复杂问题转人工。')
  await fields[1].setValue('6 周上线，客户数据不出内网')
  await fields[2].setValue('以真实工单验收，答案可追溯')
  await wrapper.find('.modal-actions .primary').trigger('click');await flushPromises()
  const payload = JSON.parse(request.mock.calls.find(([path])=>path === '/api/v1/interviews')[1].body)
  expect(payload.interview_mode).toBe('BUSINESS_SCENARIO')
  expect(payload.business_scenario).toEqual({requirement:fields[0].element.value,constraints:fields[1].element.value,success_criteria:fields[2].element.value})
  expect(payload.resume_id).toBeNull();expect(payload.resume_text).toBe('')
  expect(router.currentRoute.value.path).toBe('/interview/created')
})

it('preserves each mode draft across switching and saving but only submits the active material', async () => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  await wrapper.find('.resume-section textarea').setValue('已经填写的个人项目经历')
  await modeButton('企业业务').trigger('click')
  await wrapper.find('#business-requirement').setValue('企业希望建设一个面向销售团队的知识库问答系统。')
  await modeButton('简历经历').trigger('click')
  expect(wrapper.find('.resume-section textarea').element.value).toBe('已经填写的个人项目经历')
  await modeButton('企业业务').trigger('click')
  await wrapper.find('.modal-actions .secondary').trigger('click')
  expect(wrapper.find('.hero .pill').text()).toContain('企业业务')
  await wrapper.find('.hero-actions .secondary').trigger('click')
  expect(wrapper.find('#business-requirement').element.value).toContain('销售团队')
  await wrapper.find('.modal-actions .primary').trigger('click');await flushPromises()
  const payload = JSON.parse(request.mock.calls.find(([path])=>path === '/api/v1/interviews')[1].body)
  expect(payload.resume_text).toBe('');expect(payload.resume_id).toBeNull()
})

it('requires meaningful business input and retains it when interview creation fails', async () => {
  await wrapper.find('.hero-actions .secondary').trigger('click')
  await modeButton('企业业务').trigger('click')
  await wrapper.find('.modal-actions .primary').trigger('click');await flushPromises()
  expect(wrapper.find('#business-error').text()).toContain('至少用 10 个字')
  expect(request.mock.calls.some(([path])=>path === '/api/v1/interviews')).toBe(false)
  await wrapper.find('#business-requirement').setValue('公司需要一个私有化部署的销售知识库问答系统。')
  request.mockRejectedValueOnce(new Error('模型暂忙'))
  await wrapper.find('.modal-actions .primary').trigger('click');await flushPromises()
  expect(wrapper.find('#business-requirement').element.value).toContain('私有化部署')
  expect(wrapper.find('.config-body .error').text()).toContain('模型暂忙')
  await wrapper.find('.modal-actions .primary').trigger('click');await flushPromises()
  expect(router.currentRoute.value.path).toBe('/interview/created')
})
