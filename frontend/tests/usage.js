// Development-only fixture: deterministic sample ledgers; no backend requests or credentials.
import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from '../src/App.vue'
import TeacherUsage from '../src/views/TeacherUsage.vue'
import '../src/style.css'
if (!import.meta.env.DEV) throw new Error('Development fixture only')
const today = new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'})
const names = ['陈一诺','林雨桐','周子航','王梓涵','李沐辰','赵思远','刘若曦','张亦凡','吴清扬','许星辰','孙安然','郑予墨']
const items=names.map((name,i)=>({user_id:`s${i}`,display_name:name,username:`student_${String(i+1).padStart(3,'0')}`,class_name:i%3===0?'AI 应用开发 · 一班':i%3===1?'AI 应用开发 · 二班':'',tokens:0}))
const daily=items.flatMap((item,i)=>i===11?[]:Array.from({length:16},(_,j)=>{
  const tokens=Math.round((12000-i*700)*(0.6+(j%5)/4))
  return {user_id:item.user_id,date:new Date(Date.parse(`${today}T12:00:00Z`)-j*86400000).toISOString().slice(0,10),tokens,prompt_tokens:Math.round(tokens*.7),completion_tokens:tokens-Math.round(tokens*.7)}
}))
items.forEach(item=>item.tokens=daily.filter(d=>d.user_id===item.user_id).reduce((s,d)=>s+d.tokens,0))
const staff_items=[{user_id:'t1',display_name:'王老师',username:'teacher_wang',role:'TEACHER',tokens:28600},{user_id:'admin',display_name:'管理员',username:'admin',role:'ADMIN',tokens:0}]
window.fetch=async input=>{
 const url=new URL(input,location.origin)
 if(url.pathname!=='/api/v1/teacher/usage')throw new Error(`No fixture: ${url.pathname}`)
 const staff=url.searchParams.get('audience')==='staff'
 return new Response(JSON.stringify({items:staff?[]:items,daily:staff?[]:daily,staff_items:staff?staff_items:[],staff_daily:staff?[{user_id:'t1',date:today,tokens:28600,prompt_tokens:24000,completion_tokens:4600}]:[],as_of_date:today}),{headers:{'Content-Type':'application/json'}})
}
const router=createRouter({history:createWebHashHistory(),routes:[{path:'/teacher/usage',component:TeacherUsage},{path:'/teacher/staff-usage',component:TeacherUsage,props:{audience:'staff'}},{path:'/:pathMatch(.*)*',component:{template:'<p>用量页面布局测试</p>'}}]})
createApp(App).use(router).mount('#app')
