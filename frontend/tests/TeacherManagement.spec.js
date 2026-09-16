// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import TeacherUsage from '../src/views/TeacherUsage.vue'
import TeacherClasses from '../src/views/TeacherClasses.vue'
import App from '../src/App.vue'

const { request } = vi.hoisted(() => ({request:vi.fn()}))
vi.mock('../src/api', () => ({request}))
let wrapper
beforeEach(() => {vi.clearAllMocks(); localStorage.clear()})
afterEach(() => {wrapper?.unmount(); localStorage.clear()})

it('shows names and zero usage students, and expands the correct daily bill', async () => {
  request.mockResolvedValue({items:[{user_id:'one',display_name:'小明',username:'ming',class_name:'一班',tokens:300},{user_id:'two',display_name:'小红',username:'hong',class_name:'二班',tokens:0}],daily:[{user_id:'one',date:'2026-09-15',prompt_tokens:200,completion_tokens:100,tokens:300}]})
  wrapper = mount(TeacherUsage); await flushPromises()
  expect(wrapper.text()).toContain('小明'); expect(wrapper.text()).toContain('小红')
  expect(wrapper.find('.daily-table').exists()).toBe(false)
  await wrapper.findAll('.student-name')[0].trigger('click')
  expect(wrapper.find('.daily-table').text()).toContain('2026-09-15')
  await wrapper.findAll('.student-name')[1].trigger('click')
  expect(wrapper.text()).toContain('暂无 Token 消耗')
  await wrapper.find('input').setValue('一班')
  expect(wrapper.findAll('.usage-table tbody tr')).toHaveLength(1)
})

it('lists existing and empty classes and sends a student transfer', async () => {
  const student = {user_id:'s1',display_name:'小明',username:'ming',class_name:'一班'}
  request.mockImplementation(async (path, opts) => {
    if (opts?.method === 'PATCH') {student.class_name = JSON.parse(opts.body).class_name; return {}}
    return {items:[{name:'一班',students:student.class_name === '一班' ? [student] : []},{name:'二班',students:student.class_name === '二班' ? [student] : []}],unassigned:[]}
  })
  wrapper = mount(TeacherClasses); await flushPromises()
  expect(wrapper.text()).toContain('2 个班级 · 1 名学生')
  await wrapper.find('[aria-label="小明的班级"]').setValue('二班'); await flushPromises()
  expect(request).toHaveBeenCalledWith('/api/v1/teacher/users/s1/class',expect.objectContaining({method:'PATCH',body:JSON.stringify({class_name:'二班'})}))
  expect(wrapper.findAll('.library-item')[1].text()).toContain('小明')
})

it('greets the student after navigating from login without reloading the app', async () => {
  request.mockResolvedValue({items:[],dates:{}})
  const router = createRouter({history:createMemoryHistory(),routes:[{path:'/:pathMatch(.*)*',component:{template:'<div />'}}]})
  await router.push('/login'); await router.isReady()
  wrapper = mount(App,{global:{plugins:[router]}})
  localStorage.setItem('mianmian-user',JSON.stringify({display_name:'小明',username:'ming',role:'STUDENT'}))
  await router.push('/'); await flushPromises()
  expect(wrapper.find('h1').text()).toBe('小明，今天也来练一场')
  await router.push('/teacher/classes'); await flushPromises()
  expect(wrapper.find('h1').text()).toBe('班级管理')
})

const ledger = () => ({
  as_of_date:'2026-09-16',
  items:[{user_id:'one',display_name:'小明',username:'ming',class_name:'一班',tokens:300},{user_id:'two',display_name:'小红',username:'hong',class_name:'二班',tokens:100},{user_id:'zero',display_name:'未使用学生',username:'zero',class_name:'',tokens:0}],
  daily:[{user_id:'one',date:'2026-09-16',prompt_tokens:120,completion_tokens:80,tokens:200},{user_id:'one',date:'2026-09-01',prompt_tokens:60,completion_tokens:40,tokens:100},{user_id:'two',date:'2026-09-15',prompt_tokens:60,completion_tokens:40,tokens:100}],
  staff_items:[{user_id:'teacher',display_name:'王老师',username:'wang',role:'TEACHER',tokens:9000}],
  staff_daily:[{user_id:'teacher',date:'2026-09-16',prompt_tokens:8000,completion_tokens:1000,tokens:9000}]
})
it('keeps student and teacher totals separate and updates all cards with the class filter', async () => {
  request.mockResolvedValue(ledger());wrapper=mount(TeacherUsage);await flushPromises()
  expect(wrapper.text()).not.toContain('王老师')
  expect(wrapper.findAll('.metric > strong').map(el=>el.text())).toEqual(['400','200','300','2 / 3'])
  await wrapper.findAll('select')[0].setValue('一班')
  expect(wrapper.findAll('.metric > strong').map(el=>el.text())).toEqual(['300','200','200','1 / 1'])
  expect(wrapper.findAll('.usage-table tbody tr')).toHaveLength(1)
  await wrapper.find('.student-name').trigger('click')
  expect(wrapper.find('.daily-table').text()).toContain('2026-09-16')
  await wrapper.findAll('select')[0].setValue('__unassigned')
  expect(wrapper.find('.daily-table').exists()).toBe(false)
  expect(wrapper.find('.usage-table').text()).toContain('未使用学生')
  await wrapper.setProps({audience:'staff'});await flushPromises()
  expect(request).toHaveBeenLastCalledWith('/api/v1/teacher/usage?audience=staff',expect.any(Object))
  expect(wrapper.text()).not.toContain('小明');expect(wrapper.text()).toContain('王老师')
  expect(wrapper.findAll('.metric > strong')[0].text()).toBe('9,000')
  await wrapper.find('.student-name').trigger('click')
  expect(wrapper.find('.daily-table').text()).toContain('8,000')
})
it('paginates the roster, resets page on search, and sorts by recent activity', async () => {
  const data=ledger()
  data.items.push(...Array.from({length:11},(_,i)=>({user_id:`extra${i}`,display_name:`学生${i}`,username:`extra${i}`,tokens:0})))
  request.mockResolvedValue(data);wrapper=mount(TeacherUsage);await flushPromises()
  expect(wrapper.findAll('.usage-table tbody tr')).toHaveLength(10)
  await wrapper.find('[aria-label="下一页账号"]').trigger('click')
  expect(wrapper.findAll('.usage-table tbody tr')).toHaveLength(4)
  await wrapper.find('input').setValue('小明')
  expect(wrapper.findAll('.usage-table tbody tr')).toHaveLength(1)
  expect(wrapper.find('[aria-label="上一页账号"]').attributes('disabled')).toBeDefined()
  await wrapper.find('input').setValue('')
  await wrapper.findAll('select')[1].setValue('recent')
  expect(wrapper.findAll('.student-name')[0].text()).toBe('小明')
})
it('ignores late student responses after switching to teacher usage', async () => {
  let resolveOld;request.mockImplementationOnce(()=>new Promise(r=>{resolveOld=r})).mockResolvedValue(ledger())
  wrapper=mount(TeacherUsage);await wrapper.setProps({audience:'staff'});await flushPromises()
  resolveOld({items:ledger().items,daily:ledger().daily});await flushPromises()
  expect(wrapper.text()).toContain('王老师');expect(wrapper.text()).not.toContain('小明')
})
it('preserves the last successful ledger when refreshing fails', async () => {
  request.mockResolvedValue(ledger());wrapper=mount(TeacherUsage);await flushPromises()
  request.mockRejectedValueOnce(new Error('网络不可用'));await wrapper.find('.refresh').trigger('click');await flushPromises()
  expect(wrapper.find('[role="alert"]').text()).toContain('保留上次成功加载的数据')
  expect(wrapper.findAll('.metric > strong')[0].text()).toBe('400')
})

it('paginates daily bills and resets the detail page when changing the person', async () => {
  const data=ledger()
  data.daily=Array.from({length:15},(_,i)=>({user_id:'one',date:`2026-08-${String(i+1).padStart(2,'0')}`,tokens:20,prompt_tokens:15,completion_tokens:5}))
  request.mockResolvedValue(data);wrapper=mount(TeacherUsage);await flushPromises()
  await wrapper.findAll('.student-name')[0].trigger('click')
  expect(wrapper.findAll('.daily-table tbody tr')).toHaveLength(10)
  expect(wrapper.find('.daily-table tbody tr').text()).toContain('2026-08-15')
  await wrapper.find('[aria-label="下一页每日账单"]').trigger('click')
  expect(wrapper.findAll('.daily-table tbody tr')).toHaveLength(5)
  await wrapper.findAll('.student-name')[1].trigger('click')
  expect(wrapper.text()).toContain('暂无 Token 消耗')
  await wrapper.findAll('.student-name')[0].trigger('click')
  expect(wrapper.find('[aria-label="上一页每日账单"]').attributes('disabled')).toBeDefined()
})
