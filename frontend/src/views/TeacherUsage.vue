<template>
  <section class="usage-page teacher-page" :aria-busy="loading">
    <div class="usage-heading"><div><span class="section-kicker">{{ isStaff ? 'TEACHING USAGE' : 'STUDENT USAGE' }}</span><h2>{{ isStaff ? '教学用量，一目了然' : '每一份练习，都有迹可循' }}</h2><p>{{ isStaff ? '教师与管理员的备课、题库解析及参考答案生成用量。' : '按班级掌握学生用量，点击姓名查看每天的消耗。' }}</p></div><button class="secondary refresh" :disabled="loading" @click="load"><RefreshCw :size="16" />{{ loading ? '正在刷新…' : '刷新数据' }}</button></div>
    <p v-if="error" class="error" role="alert">{{ error }}{{ loaded ? '；下方保留上次成功加载的数据。' : '' }}</p>
    <p v-if="loading && !loaded" class="notice" role="status">正在读取用量记录…</p>
    <template v-if="loaded">
      <div class="scope-caption"><span>{{ isStaff ? '教师及管理员' : selectedClass ? (selectedClass === '__unassigned' ? '未分班学生' : selectedClass) : '全部班级' }} · {{ filtered.length }} 名{{ person }}{{ search ? ' · 已应用搜索' : '' }}</span><span>北京时间 · 截至 {{ today }}</span></div>
      <div class="usage-metrics">
        <article class="metric featured"><span>累计消耗 <small>Token</small></span><strong>{{ number(summary.total) }}</strong><p>当前筛选范围内的历史用量</p></article>
        <article class="metric"><span>今日消耗 <small>Token</small></span><strong>{{ number(summary.today) }}</strong><p>{{ today }} · 北京时间</p></article>
        <article class="metric"><span>近 7 天消耗 <small>Token</small></span><strong>{{ number(summary.week) }}</strong><p>{{ weekDates[0] }} 至 {{ today }}</p></article>
        <article class="metric"><span>近 7 天使用人数</span><strong>{{ summary.active }}<small> / {{ filtered.length }}</small></strong><p>{{ isStaff ? '有模型调用记录的账号' : '有模型调用记录的学生' }}</p></article>
      </div>
      <div class="usage-layout">
        <section class="roster-card">
          <div class="list-heading"><h3>{{ person }}用量排行</h3><span>{{ {total: '累计消耗从高到低', today: '今日消耗从高到低', recent: '最近使用优先', name: '按姓名排列'}[sort] }}</span></div>
          <div class="usage-filters">
            <label class="search-field"><span>查找{{ person }}</span><div><Search :size="16" aria-hidden="true" /><input v-model.trim="search" :placeholder="isStaff ? '姓名或用户名' : '姓名、用户名或班级'" /></div></label>
            <label v-if="!isStaff"><span>班级</span><select v-model="selectedClass"><option value="">全部班级</option><option value="__unassigned">未分班</option><option v-for="name in classes" :key="name" :value="name">{{ name }}</option></select></label>
            <label><span>排序</span><select v-model="sort"><option value="total">累计消耗最多</option><option value="today">今日消耗最多</option><option value="recent">最近使用优先</option><option value="name">姓名顺序</option></select></label>
          </div>
          <div v-if="!filtered.length" class="empty-state"><Users :size="28" /><h4>{{ rows.length ? '没有匹配的账号' : `暂无${person}账号` }}</h4><p>{{ rows.length ? '试试其他姓名或班级。' : '分配账号后，即可在这里查看用量。' }}</p><button v-if="rows.length" class="secondary" @click="resetFilters">清空筛选</button></div>
          <div v-else class="table-scroll">
            <table class="usage-table"><caption class="sr-only">{{ person }} Token 消耗，点击姓名查看每日明细</caption><thead><tr><th scope="col">{{ person }}</th><th scope="col">{{ isStaff ? '角色' : '班级' }}</th><th scope="col" class="numeric">累计 Token</th><th scope="col" class="numeric">今日 Token</th><th scope="col">最近使用</th></tr></thead>
              <tbody><tr v-for="item in paged" :key="item.user_id" :class="{selected: selectedId === item.user_id}"><td><button class="student-name" :id="`usage-person-${item.user_id}`" :aria-label="`查看${nameOf(item)}的每日明细`" :aria-pressed="selectedId === item.user_id" aria-controls="usage-detail" @click="selectPerson(item)">{{ nameOf(item) }}<ChevronRight :size="14" aria-hidden="true" /></button><small class="username">{{ item.username }}</small></td><td class="account-group" :data-label="isStaff ? '角色' : '班级'"><span class="class-tag">{{ isStaff ? (item.role === 'ADMIN' ? '管理员' : '教师') : item.class_name || '未分班' }}</span></td><td class="numeric" data-label="累计 Token"><strong>{{ number(item.tokens) }}</strong><span class="usage-meter" aria-hidden="true"><i :style="{width: `${maxTokens ? item.tokens / maxTokens * 100 : 0}%`}" /></span></td><td class="numeric" data-label="今日 Token">{{ number(item.today) }}</td><td class="last-used" data-label="最近使用">{{ item.lastUsed || '尚未使用' }}</td></tr></tbody>
            </table>
          </div>
          <div v-if="filtered.length" class="pagination"><span>共 {{ filtered.length }} 人 · 每页 10 人</span><div><button class="secondary" aria-label="上一页账号" :disabled="page === 1" @click="page--"><ChevronLeft :size="16" /></button><span>{{ page }} / {{ pages }}</span><button class="secondary" aria-label="下一页账号" :disabled="page === pages" @click="page++"><ChevronRight :size="16" /></button></div></div>
        </section>
        <aside id="usage-detail" class="detail-card">
          <div v-if="!selected" class="detail-placeholder"><ChartColumnIncreasing :size="32" /><h3>查看每日明细</h3><p>点击列表中的{{ person }}姓名，查看累计用量、近 7 天趋势和每日账单。</p><span>输入与输出 Token 分开统计</span></div>
          <template v-else>
            <div class="detail-heading"><div><span class="section-kicker">DAILY BREAKDOWN</span><h3 ref="detailTitle" tabindex="-1">{{ nameOf(selected) }}</h3><p>{{ selected.username }} · {{ isStaff ? (selected.role === 'ADMIN' ? '管理员' : '教师') : selected.class_name || '未分班' }}</p></div><button class="close-detail" aria-label="关闭每日明细" @click="closeDetail"><X :size="18" /></button></div>
            <div class="detail-total"><span>累计 Token</span><strong>{{ number(selected.tokens) }}</strong></div>
            <div class="token-split"><div><span>输入 Token</span><strong>{{ number(selectedTotals.prompt) }}</strong></div><div><span>输出 Token</span><strong>{{ number(selectedTotals.completion) }}</strong></div></div>
            <div class="trend-heading"><h4>近 7 天用量</h4><span>含今日</span></div>
            <div class="trend-chart" role="img" :aria-label="trend.map(d => `${d.date}：${number(d.tokens)} Token`).join('；')"><div v-for="day in trend" :key="day.date" class="trend-column" :title="`${day.date} · ${number(day.tokens)} Token`"><div class="bar-track"><i :style="{height: `${day.tokens ? Math.max(3, day.tokens / trendMax * 100) : 0}%`}" /></div><small>{{ day.date.slice(5).replace('-', '/') }}</small></div></div>
            <div class="trend-heading"><h4>每日账单</h4><span>最近日期优先</span></div>
            <p v-if="!selectedDays.length" class="no-usage">暂无 Token 消耗，使用模型后会记录在这里。</p>
            <div v-else class="table-scroll"><table class="daily-table"><thead><tr><th scope="col">日期</th><th scope="col" class="numeric">输入</th><th scope="col" class="numeric">输出</th><th scope="col" class="numeric">合计</th></tr></thead><tbody><tr v-for="day in pagedDays" :key="day.date"><td>{{ day.date }}</td><td class="numeric">{{ number(day.prompt_tokens) }}</td><td class="numeric">{{ number(day.completion_tokens) }}</td><td class="numeric">{{ number(day.tokens) }}</td></tr></tbody></table></div>
            <div v-if="selectedDays.length" class="pagination detail-pagination"><span>共 {{ selectedDays.length }} 天</span><div><button class="secondary" aria-label="上一页每日账单" :disabled="dayPage === 1" @click="dayPage--"><ChevronLeft :size="14" /></button><span>{{ dayPage }} / {{ dayPages }}</span><button class="secondary" aria-label="下一页每日账单" :disabled="dayPage === dayPages" @click="dayPage++"><ChevronRight :size="14" /></button></div></div>
          </template>
        </aside>
      </div>
      <p class="ledger-note"><Info :size="15" aria-hidden="true" />仅统计 DeepSeek 实际返回的 Token 用量。{{ isStaff ? '不包含学生面试及重答用量。' : '包含面试、报告、题目复习与重答、临时知识库解析，不包含教师用量。' }}语音识别与朗读费用不计入。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ChartColumnIncreasing, ChevronLeft, ChevronRight, Info, RefreshCw, Search, Users, X } from 'lucide-vue-next'
import { request } from '../api'
const props = defineProps({ audience: { type: String, default: 'student' } })
const isStaff = computed(() => props.audience === 'staff'), person = computed(() => isStaff.value ? '教师' : '学生')
const items = ref([]), daily = ref([]), loading = ref(false), loaded = ref(false), error = ref(''), today = ref('')
const search = ref(''), selectedClass = ref(''), sort = ref('total'), page = ref(1), selectedId = ref(''), dayPage = ref(1), detailTitle = ref(null)
let controller, version = 0
const number = value => Number(value || 0).toLocaleString('zh-CN')
const nameOf = item => item.display_name || item.username
const weekDates = computed(() => Array.from({length:7}, (_,i) => new Date(Date.parse(`${today.value}T12:00:00Z`) - (6-i)*86400000).toISOString().slice(0,10)))
const dailyByUser = computed(() => {
  const map = new Map()
  for (const day of daily.value) {
    if (!map.has(day.user_id)) map.set(day.user_id, [])
    map.get(day.user_id).push(day)
  }
  for (const days of map.values()) days.sort((a,b) => b.date.localeCompare(a.date))
  return map
})
const rows = computed(() => items.value.map(item => {
  const days = dailyByUser.value.get(item.user_id) || []
  return {...item, tokens: Number(item.tokens || 0), today: days.find(d=>d.date === today.value)?.tokens || 0,
    week: days.filter(d=>d.date >= weekDates.value[0] && d.date <= today.value).reduce((s,d)=>s+d.tokens,0),
    lastUsed: days.find(d=>d.tokens>0)?.date || ''}
}))
const classes = computed(() => [...new Set(items.value.map(i=>i.class_name).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN')))
const filtered = computed(() => rows.value.filter(item => [item.display_name,item.username,isStaff.value ? '' : item.class_name].join(' ').toLowerCase().includes(search.value.toLowerCase()) &&
  (isStaff.value || !selectedClass.value || (selectedClass.value === '__unassigned' ? !item.class_name : item.class_name === selectedClass.value))).sort((a,b)=>{
    if (sort.value === 'name') return nameOf(a).localeCompare(nameOf(b),'zh-CN')
    return (sort.value === 'recent' ? b.lastUsed.localeCompare(a.lastUsed) : sort.value === 'today' ? b.today-a.today : b.tokens-a.tokens) || nameOf(a).localeCompare(nameOf(b),'zh-CN')
  }))
const summary = computed(() => filtered.value.reduce((s,i)=>({total:s.total+i.tokens,today:s.today+i.today,week:s.week+i.week,active:s.active+(i.week>0?1:0)}),{total:0,today:0,week:0,active:0}))
const maxTokens = computed(() => Math.max(0,...filtered.value.map(i=>i.tokens)))
const pages = computed(()=>Math.max(1,Math.ceil(filtered.value.length/10)))
const paged = computed(()=>filtered.value.slice((page.value-1)*10,page.value*10))
const selected = computed(()=>filtered.value.find(i=>i.user_id === selectedId.value))
const selectedDays = computed(()=>selected.value ? dailyByUser.value.get(selectedId.value) || [] : [])
const selectedTotals = computed(()=>selectedDays.value.reduce((s,d)=>({prompt:s.prompt+d.prompt_tokens,completion:s.completion+d.completion_tokens}),{prompt:0,completion:0}))
const trend = computed(()=>weekDates.value.map(date=>({date,tokens:selectedDays.value.find(d=>d.date === date)?.tokens || 0})))
const trendMax = computed(()=>Math.max(1,...trend.value.map(d=>d.tokens)))
const dayPages = computed(()=>Math.max(1,Math.ceil(selectedDays.value.length/10)))
const pagedDays = computed(()=>selectedDays.value.slice((dayPage.value-1)*10,dayPage.value*10))
function resetFilters(){ search.value='';selectedClass.value='';sort.value='total' }
async function selectPerson(item){ selectedId.value=item.user_id;dayPage.value=1;await nextTick();detailTitle.value?.focus({preventScroll:true});detailTitle.value?.scrollIntoView?.({block:'nearest',behavior:'smooth'}) }
async function closeDetail(){ const id=selectedId.value;selectedId.value='';await nextTick();document.getElementById(`usage-person-${id}`)?.focus() }
watch([search,selectedClass,sort],()=>{page.value=1;selectedId.value='';dayPage.value=1})
async function load(){
  const current=++version;controller?.abort();controller=new AbortController();loading.value=true;error.value=''
  try {
    const data=await request(`/api/v1/teacher/usage?audience=${props.audience}`,{signal:controller.signal})
    if(current!==version)return
    items.value=(isStaff.value ? data.staff_items : data.items) || []
    daily.value=(isStaff.value ? data.staff_daily : data.daily) || []
    today.value=data.as_of_date || new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'})
    loaded.value=true;page.value=Math.min(page.value,pages.value);dayPage.value=Math.min(dayPage.value,dayPages.value)
    if(!selected.value)selectedId.value=''
  } catch(e){if(current===version && e.name!=='AbortError')error.value=e.message}
  finally{if(current===version)loading.value=false}
}
watch(()=>props.audience,()=>{items.value=[];daily.value=[];loaded.value=false;selectedId.value='';page.value=1;dayPage.value=1;resetFilters();load()},{immediate:true})
onBeforeUnmount(()=>{version++;controller?.abort()})
</script>

<style scoped>
.usage-page { color: #34473b; }
.usage-heading { display:flex; justify-content:space-between; align-items:center; gap:20px; flex-wrap:wrap; margin-bottom:28px; }
.usage-heading h2 { font-size:clamp(21px,1.65vw,28px); margin-top:9px; letter-spacing:0; }
.usage-heading p { font-size:14px; color:#798378; line-height:1.8; margin-top:10px; }
.refresh { gap:8px; background:#fff; border:1px solid #dfe5d9; }
.scope-caption { display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; font-size:12px; color:#7c8777; margin-bottom:12px; }
.usage-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-bottom:24px; }
.metric { border:1px solid #e0e6da; background:#fff; border-radius:12px; padding:22px; min-width:0; }
.metric > span { font-size:13px; color:#728169; display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
.metric > span small { font-size:10px; color:#8d9785; }
.metric > strong { display:block; font-size:clamp(23px,2vw,34px); font-weight:600; font-variant-numeric:tabular-nums; margin:14px 0 10px; overflow-wrap:anywhere; letter-spacing:-.7px; }
.metric > strong small { font-size:16px; font-weight:400; color:#85917d; }
.metric p { font-size:11px; line-height:1.8; color:#8b9582; }
.metric.featured { background:#344e3f; border-color:#344e3f; color:#fff; }.featured > span,.featured > span small,.featured p { color:#c0cdbc; }
.usage-layout { display:grid; grid-template-columns:minmax(0,1.65fr) minmax(340px,1fr); gap:22px; align-items:start; }
.roster-card,.detail-card { background:#fff; border:1px solid #e0e6da; border-radius:14px; overflow:hidden; min-width:0; }
.list-heading { padding:24px 24px 0; display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }.list-heading h3,.detail-heading h3 { font-size:18px; }.list-heading > span { color:#8d9587; font-size:12px; }
.usage-filters { display:flex; align-items:end; flex-wrap:wrap; gap:12px; padding:20px 24px; }.usage-filters label { flex:1 1 125px; min-width:0; }.usage-filters .search-field { flex:1.5 1 190px; }.usage-filters label > span { display:block; color:#718168; font-size:12px; margin-bottom:8px; }
.usage-filters select,.search-field > div { border:1px solid #dfe5d9; border-radius:7px; height:42px; width:100%; background:#fff; }.usage-filters select { padding:0 9px; font-size:13px; color:#526449; }.search-field > div { display:flex; align-items:center; padding:0 12px; gap:8px; color:#919c89; }.search-field input { border:0; outline:0; min-width:0; width:100%; font-size:13px; background:transparent; }.search-field > div:focus-within { outline:2px solid #a4b89b; }
.table-scroll { overflow-x:auto; max-width:100%; }table { width:100%; border-collapse:collapse; font-size:13px; }th { font-size:11px; font-weight:500; color:#86917f; background:#f7f9f4; }th,td { text-align:left; padding:16px 18px; border-bottom:1px solid #edf0e7; }th { white-space:nowrap; }td { vertical-align:middle; }td strong { font-variant-numeric:tabular-nums; font-weight:600; }.numeric { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }.selected { background:#f0f6ec; }.usage-table tbody tr:hover { background:#f7f9f4; }.usage-table td:first-child { min-width:150px; }.usage-table td:nth-child(2) { max-width:170px; min-width:95px; }
.student-name { display:flex; align-items:center; gap:5px; padding:0; background:none; font-size:14px; color:#3d6247; font-weight:600; text-align:left; overflow-wrap:anywhere; line-height:1.6; }.student-name svg { flex-shrink:0; color:#9cab92; }.username { display:block; font-size:11px; color:#8a9581; margin-top:5px; overflow-wrap:anywhere; max-width:180px; }.class-tag { font-size:11px; line-height:1.7; color:#7c886f; overflow-wrap:anywhere; }.last-used { white-space:nowrap; font-size:11px; color:#86937a; }.usage-meter { display:block; width:70px; height:3px; margin:9px 0 0 auto; background:#e8eedf; border-radius:3px; }.usage-meter i { display:block; height:100%; border-radius:3px; background:#9cb68d; }
.pagination { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; padding:18px 24px; font-size:12px; color:#8a9481; }.pagination > div { display:flex; align-items:center; gap:10px; }.pagination .secondary { min-height:30px; padding:6px; background:#f5f7f1; }
.detail-card { padding:24px; }.detail-placeholder { min-height:440px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; color:#91a185; }.detail-placeholder > svg { margin-bottom:20px; }.detail-placeholder h3 { font-size:17px; color:#617454; }.detail-placeholder p { font-size:13px; line-height:1.9; margin:15px 0; max-width:245px; }.detail-placeholder > span { border-top:1px solid #e6ebdf; padding-top:16px; font-size:11px; }
.detail-heading { display:flex; justify-content:space-between; gap:14px; }.detail-heading > div { min-width:0; }.detail-heading h3 { margin-top:9px; overflow-wrap:anywhere; }.detail-heading p { font-size:12px; color:#8b957f; line-height:1.8; margin-top:8px; overflow-wrap:anywhere; }.close-detail { align-self:start; color:#8c9980; background:#f4f7ef; padding:6px; border-radius:6px; display:flex; }.detail-total { margin-top:24px; }.detail-total span { color:#7e8e71; font-size:12px; }.detail-total strong { display:block; font-size:32px; letter-spacing:-.5px; font-weight:600; margin-top:8px; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }.token-split { display:grid; grid-template-columns:1fr 1fr; gap:14px; border-bottom:1px solid #e9eddf; padding:18px 0 24px; }.token-split span { display:block; font-size:11px; color:#929d87; }.token-split strong { display:block; font-size:15px; margin-top:8px; font-weight:500; overflow-wrap:anywhere; }
.trend-heading { display:flex; justify-content:space-between; align-items:center; gap:10px; margin:24px 0 14px; }.trend-heading h4 { font-size:13px; font-weight:600; }.trend-heading > span { color:#9aa28f; font-size:10px; }.trend-chart { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:8px; }.trend-column { min-width:0; text-align:center; }.bar-track { height:76px; display:flex; align-items:end; justify-content:center; border-bottom:1px solid #e2e8da; }.bar-track i { display:block; width:70%; max-width:28px; background:#a5bc92; border-radius:3px 3px 0 0; }.trend-column:last-child i { background:#526f43; }.trend-column small { display:block; margin-top:8px; font-size:10px; color:#8d9a80; }.daily-table { font-size:11px; white-space:nowrap; }.daily-table th,.daily-table td { padding:12px 8px; }.daily-table td:last-child { font-weight:600; }.detail-pagination { padding:16px 0 0; }.no-usage { font-size:13px; color:#8a977c; line-height:1.9; }.empty-state { padding:70px 24px; color:#94a385; text-align:center; }.empty-state h4 { margin-top:15px; color:#6c7d5f; }.empty-state p { margin:12px 0 20px; font-size:13px; }.ledger-note { display:flex; align-items:start; gap:8px; font-size:11px; color:#8a9580; line-height:1.9; margin-top:20px; }.ledger-note svg { flex-shrink:0; margin-top:3px; }.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }
@media(max-width:1200px){ .usage-layout { grid-template-columns:minmax(0,1fr); }.detail-placeholder { min-height:200px; }.usage-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media(max-width:600px){ .usage-heading { margin-bottom:22px; }.metric { padding:16px; }.metric > strong { font-size:24px; }.usage-metrics { gap:10px; }.list-heading { padding:20px 16px 0; }.usage-filters { padding:18px 16px; }.usage-filters .search-field { flex-basis:100%; }.search-field input,.usage-filters select { font-size:16px; }.detail-card { padding:20px 16px; }th,td { padding:14px 12px; }.pagination { padding:16px; }.detail-pagination { padding:16px 0 0; } }
@media(max-width:600px){
  .usage-table thead { position:absolute; width:1px; height:1px; clip:rect(0,0,0,0); overflow:hidden; }
  .usage-table,.usage-table tbody { display:block; }
  .usage-table tbody tr { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); padding:16px; gap:10px 16px; border-top:1px solid #edf0e7; }
  .usage-table td { display:block; border:0; padding:0; min-width:0; max-width:none; text-align:left; }
  .usage-table td:first-child,.usage-table td:nth-child(2) { min-width:0; max-width:none; }
  .usage-table td:first-child,.usage-table .account-group,.usage-table .last-used { grid-column:1 / -1; }
  .usage-table td::before { content:attr(data-label); display:block; font-size:11px; color:#86917f; font-weight:400; margin-bottom:6px; }
  .usage-table td:first-child::before { display:none; }
  .usage-table .account-group::before,.usage-table .last-used::before { display:inline; margin-right:8px; }
  .usage-meter { margin-left:0; }.username { max-width:none; }.usage-table .student-name { font-size:16px; }
}
@media(prefers-reduced-motion:reduce){ * { scroll-behavior:auto; } }
</style>
