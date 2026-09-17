// Development-only visual fixture. No requests or credentials are sent to the backend.
import { createApp, nextTick } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from '../src/App.vue'
import Workspace from '../src/views/Workspace.vue'
import Teacher from '../src/views/Teacher.vue'
import TeacherReports from '../src/views/TeacherReports.vue'
import TeacherAccounts from '../src/views/TeacherAccounts.vue'
import TeacherClasses from '../src/views/TeacherClasses.vue'
import TeacherEvaluation from '../src/views/TeacherEvaluation.vue'
import TeacherUsage from '../src/views/TeacherUsage.vue'
import Login from '../src/views/Login.vue'
import TeacherLogin from '../src/views/TeacherLogin.vue'
import Report from '../src/views/Report.vue'
import Interview from '../src/views/Interview.vue'
import Bookmarks from '../src/views/Bookmarks.vue'
import '../src/style.css'

if (!import.meta.env.DEV) throw new Error('Visual fixtures are only available in development')
const question = '如何设计一个支持多个业务部门的企业知识库问答系统，并在高并发场景下平衡检索准确率、响应延迟与推理成本？'
const answer = '先以真实业务问题构建评测集，再分层评估召回、重排和生成，结合缓存与降级策略保障服务。'.repeat(4)
const dimensions = {engineering_depth:82,system_design:75,star_structure:70,stress_handling:80}
const turn = {turn:1,question,answer,score:78,dimensions,feedback:'回答能够识别检索、延迟和成本之间的取舍，但还需要把技术方案与可验证的业务目标联系起来。工程深度：说明了分层评估思路，未明确如何构建真实查询集、分析召回失败样本，以及比较混合检索与单路检索的差异。系统设计：提出缓存和降级策略，建议进一步说明缓存更新时机、权限隔离与无依据回答的处理流程。改进建议：1）先收集真实业务问题，按术语、口语问法和多轮追问分类；2）对比不同检索方案的 Recall@5、端到端延迟与单次请求成本；3）说明上线验收和回滚条件，使用实际结果解释取舍。'}
const session = {session_id:'visual',user_id:'visual',status:'IN_PROGRESS',job_track:'AI 应用开发与企业级智能体系统架构工程师',style:'ALL_ROUND',history:[turn],turn:1,target_question_count:5,started_at:new Date().toISOString(),question}
const students = [{user_id:'visual',display_name:'布局测试学生',username:'student_with_a_very_long_username_for_layout_checks',class_name:'AI 应用开发工程师就业提升 2026 年秋季进阶班',tokens:1234567}, {user_id:'empty',display_name:'零用量学生',username:'new_student',class_name:'待就业班',tokens:0}]
const date = new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'})
const questions = Array.from({length:10},(_,i)=>({id:`q${i}`,question,answer,job_track:'AI 应用开发工程师',category:'系统设计',difficulty:'HARD',source_file:'企业级智能体架构设计与面试题参考答案汇编.docx'}))
questions[9].deleted_at = new Date().toISOString()
const report = {overall_score:78,dimensions,summary:'已完成 5 轮回答，以下为本场面试评估汇总。',turns:[turn,{...turn,turn:2}],interview_summary:{conclusion:'本场回答展示了扎实的工程基础，能够关注检索、评测与服务可靠性。下一步需要把技术决策与业务验收目标结合，形成完整的证据链。',strengths:['能够结合真实问题集设计离线评估，区分召回与生成阶段的质量目标。','对服务可靠性有基本认识，能够提出缓存和降级方案。'],priorities:['补充业务验收标准，说明准确率、响应时延和成本的可接受范围。','通过量化数据说明方案取舍，而不是仅列举技术名词。'],next_steps:['整理一份验收表，为每项指标补充数据来源、阈值与评测方法。','用一个完整项目练习 STAR 表达，明确个人贡献与改进后的结果。']}}
if (new URLSearchParams(location.search).get('training') === 'business') {
  const context = {interview_mode:'BUSINESS_SCENARIO',business_scenario:{requirement:'公司希望为售后团队建设 AI 客服，回答商品和物流问题，复杂情况转人工，并接入现有客服系统。',constraints:'6 周上线，2 人开发，客户数据不能离开内网。',success_criteria:'以真实工单验收，答案可追溯，不确定的问题转人工。'}}
  Object.assign(session, context); Object.assign(report, context)
}
const review = {knowledge_points:['检索召回与重排策略','评测集构建与业务验收标准','延迟、成本和服务可靠性的取舍'],spoken_answer:'如果由我来设计，我会先和业务部门确认哪些问题值得回答，以及回答到什么程度才算可用。接着收集真实问题和参考资料，建立一套评测集。\n\n技术上，我会把检索和生成分开评估：先检查相关资料能否被召回，再看模型能否依据资料给出准确的回答。对于没有依据的问题，要能明确告知信息不足。\n\n在高并发场景下，我会根据压测结果安排缓存、限流和降级，同时观察端到端延迟和单次回答成本。最后用业务验收结果决定优先优化哪一环，而不是只追求某一个离线分数。'}
let bookmarks = [{id:'saved',session_id:'visual',turn:1,question,job_track:session.job_track,created_at:session.started_at,interview_started_at:session.started_at,status:'ready',review}]
report.turns[0].bookmark_id='saved'
const rubricItems = [
  ['需求分析',20,'澄清用户问题、业务目标与验收标准，判断需求优先级。'],
  ['产品设计',25,'设计可落地的业务流程和产品方案，说明方案取舍。'],
  ['数据与验证',20,'制定效果指标，通过数据与实验验证业务价值。'],
  ['项目交付',15,'拆解里程碑与资源安排，协调依赖并处理交付风险。'],
  ['商业判断',10,'理解收入、成本和竞争环境，识别方案的业务边界。'],
  ['沟通协作',10,'清晰表达决策依据，推动跨团队协作与复盘改进。'],
].map(([name,weight,observation],i)=>({key:`metric_${i}`,name,weight,observation,critical:i<2}))
let evaluationTemplates = []
window.fetch = async (input, options={}) => {
  const url = new URL(input, location.origin), path = url.pathname
  let data
  if (path === '/api/v1/teacher/evaluation-templates') {
    if(options.method==='PUT') {data={...JSON.parse(options.body),id:'visual-template',revision:1};evaluationTemplates=[data]}
    else data={items:evaluationTemplates,classes:students.map(s=>s.class_name)}
  }
  else if (path === '/api/v1/teacher/evaluation-templates/resolve') data={job_track:url.searchParams.get('job_track'),class_name:'',focus:'',revision:0,items:rubricItems,source:'default'}
  else if (path === '/api/v1/teacher/evaluation-templates/suggest') data={...JSON.parse(options.body),items:rubricItems}
  else if (path === '/api/v1/resumes') data = {resume_id:'visual-resume',filename:'张同学_AI应用开发工程师_企业级知识库与智能体项目经历.pdf',text:'负责企业知识库的检索、评测与服务部署。'.repeat(20)}
  else if (path === '/api/v1/student/knowledge/import') data = {knowledge_id:'visual-knowledge',filename:'大模型应用开发工程师_项目与场景专项面试题.docx',questions:questions.slice(0,3)}
  else if (path === '/api/v1/student/interviews') data = {items:[{...session,date,has_report:true,status:'COMPLETED'}, {...session,session_id:'ongoing',date,has_report:false}],dates:{[date]:2}}
  else if (path === '/api/v1/student/question-tracks') data = {items:[{job_track:'AI 应用开发工程师',question_count:41},{job_track:'Python 后端开发与智能体系统工程师',question_count:72}]}
  else if (path === '/api/v1/teacher/question-bank') {
    const items = questions.filter(q => !!q.deleted_at === (url.searchParams.get('state') === 'trash'))
    data = {items,total:items.length,page:1,tracks:['AI 应用开发工程师'],counts:{active:questions.filter(q=>!q.deleted_at).length,trash:questions.filter(q=>q.deleted_at).length}}
  }
  else if (path.startsWith('/api/v1/teacher/question-bank/') && options.method === 'POST') {
    const q = questions.find(q=>q.id===path.split('/').at(-2))
    if(path.endsWith('/trash')) q.deleted_at = new Date().toISOString()
    else delete q.deleted_at
    data = q
  }
  else if (path.startsWith('/api/v1/teacher/question-bank/') && options.method === 'DELETE') {
    questions.splice(questions.findIndex(q=>q.id===path.split('/').pop()), 1); data = {ok:true}
  }
  else if (path === '/api/v1/teacher/interviews') data = {items:students.map((student,i)=>({session_id:'visual',student,job_track:'AI 应用开发工程师',started_at:session.started_at,turn_count:5,overall_score:i ? 56 : 78})),total:2,page:1,classes:students.map(s=>s.class_name)}
  else if (path.endsWith('/draft')) data = {question:'请阐述企业级知识库问答系统的架构设计，并分析高并发场景下检索准确率、响应时延与推理成本之间的权衡。',category:'系统设计',job_track:'AI 应用开发工程师',difficulty:'HARD',answer:''}
  else if (path.endsWith('/commit')) data = {id:'collected',...JSON.parse(options.body)}
  else if (path === '/api/v1/teacher/interviews/visual/report') data = {...report,student:students[0],job_track:'AI 应用开发工程师',started_at:session.started_at}
  else if (path === '/api/v1/teacher/classes') data = {items:students.map(s=>({name:s.class_name,students:[s]})),unassigned:[]}
  else if (path === '/api/v1/teacher/usage') data = {items:students,daily:[{user_id:'visual',date,prompt_tokens:1234000,completion_tokens:567,tokens:1234567}]}
  else if (path === '/api/v1/student/bookmarks' && options.method==='POST') {
    const {turn}=JSON.parse(options.body),id=`saved-${turn}`
    data={...bookmarks[0],id,session_id:'visual',turn,question,created_at:session.started_at,interview_started_at:session.started_at,job_track:session.job_track,status:'pending',review:null}
    bookmarks.push(data);report.turns.find(t=>t.turn===turn).bookmark_id=id
  }
  else if (path === '/api/v1/student/bookmarks') data = {items:bookmarks,total:bookmarks.length,page:1,page_size:10}
  else if (path.startsWith('/api/v1/student/bookmarks/') && options.method==='DELETE') {
    const id=path.split('/').pop();bookmarks=bookmarks.filter(item=>item.id!==id)
    report.turns.forEach(t=>{if(t.bookmark_id===id)t.bookmark_id=null});data={ok:true}
  }
  else if (path.endsWith('/review')) {
    const item=bookmarks.find(item=>item.id===path.split('/').at(-2))
    await new Promise(resolve=>setTimeout(resolve,1200));Object.assign(item,{status:'ready',review});data=item
  }
  else if (path.endsWith('/evaluation-sheet')) data = {status:'ready'}
  else if (path.endsWith('/report')) data = report
  else if (path === '/api/v1/interviews/visual') data = session
  else throw new Error(`Visual fixture has no handler: ${path}`)
  return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}})
}
window.WebSocket = class {
  static OPEN = 1
  readyState = 1
  constructor() { this.timer = setTimeout(()=>{this.onopen?.();this.onmessage?.({data:JSON.stringify({type:'SESSION_STATE',payload:session})})},30) }
  close() { clearTimeout(this.timer);this.readyState=3 }
  send() {}
}
const router = createRouter({history:createWebHashHistory(),routes:[
  {path:'/',component:Workspace},{path:'/login',component:Login},{path:'/teacher/login',component:TeacherLogin},
  {path:'/teacher',component:Teacher},{path:'/teacher/accounts',component:TeacherAccounts},
  {path:'/teacher/reports',component:TeacherReports},{path:'/teacher/reports/:id',component:Report,props:{teacher:true}},
  {path:'/teacher/evaluation',component:TeacherEvaluation},
  {path:'/teacher/classes',component:TeacherClasses},{path:'/teacher/usage',component:TeacherUsage},
  {path:'/report/:id',component:Report},{path:'/interview/:id',component:Interview},
  {path:'/bookmarks',component:Bookmarks},
]})
createApp(App).use(router).mount('#app')

// Exercise upload completion with fixture responses, without real files or model calls.
if (new URLSearchParams(location.search).get('materials') === 'uploaded') {
  await router.isReady(); await nextTick()
  document.querySelector('.hero-actions .secondary').click()
  await nextTick()
  for (const selector of ['.resume-file-input', '.knowledge-file-input']) {
    const transfer = new DataTransfer()
    transfer.items.add(new File(['visual fixture'], 'example.pdf', {type:'application/pdf'}))
    const input = document.querySelector(selector)
    input.files = transfer.files
    input.dispatchEvent(new Event('change', {bubbles:true}))
    await new Promise(resolve => setTimeout(resolve, 50))
  }
}
