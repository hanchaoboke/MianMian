<template>
  <section class="practice-calendar" aria-label="面试日历">
    <div class="calendar-heading"><h2>面试日历</h2><small>北京时间</small></div>
    <div class="calendar-month"><button aria-label="上个月" @click="move(-1)">‹</button><strong>{{ year }} 年 {{ month }} 月</strong><button aria-label="下个月" @click="move(1)">›</button></div>
    <div class="calendar-week"><span v-for="day in ['一','二','三','四','五','六','日']" :key="day">{{ day }}</span></div>
    <div class="calendar-grid">
      <span v-for="n in offset" :key="`blank-${n}`" />
      <button v-for="day in days" :key="day" :class="{'has-interview': !!historyDates[key(day)], selected: selected === key(day), today: today === key(day)}" :aria-label="`${key(day)}，${historyDates[key(day)] || 0} 场面试`" :aria-pressed="selected === key(day)" :aria-current="today === key(day) ? 'date' : undefined" @click="select(day)">{{ day }}</button>
    </div>
    <p class="calendar-legend"><i />有模拟面试</p>
    <p v-if="historyLoading" class="calendar-message" role="status">正在加载记录…</p>
    <p v-if="historyError" class="calendar-message" role="alert">记录加载失败 <button @click="refreshHistory">重试</button></p>
    <button class="calendar-all" @click="router.push('/')">查看全部面试</button>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { historyDates, historyLoading, historyError, refreshHistory, shanghaiDate } from '../studentHistory'
const route = useRoute(), router = useRouter(), today = shanghaiDate()
const year = ref(Number(today.slice(0,4))), month = ref(Number(today.slice(5,7)))
const selected = computed(() => typeof route.query.date === 'string' ? route.query.date : '')
const days = computed(() => new Date(year.value, month.value, 0).getDate())
const offset = computed(() => (new Date(year.value, month.value - 1, 1).getDay() + 6) % 7)
function key(day) { return `${year.value}-${String(month.value).padStart(2,'0')}-${String(day).padStart(2,'0')}` }
function move(delta) { const next = new Date(year.value, month.value - 1 + delta, 1); year.value = next.getFullYear(); month.value = next.getMonth() + 1 }
function select(day) { router.push({path:'/', query:{date:key(day)}}) }
watch(selected, value => { if (/^\d{4}-\d{2}-\d{2}$/.test(value)) { const m = Number(value.slice(5,7)); if(m >= 1 && m <= 12) { year.value = Number(value.slice(0,4)); month.value = m } } }, {immediate:true})
</script>
<style scoped>
.practice-calendar{margin-top:28px;padding:16px 8px;background:#ffffff85;border:1px solid #e2e5dd;border-radius:12px}.calendar-heading{display:flex;justify-content:space-between;align-items:center;padding:0 5px}.calendar-heading h2{font-size:13px;letter-spacing:0}.calendar-heading small{font-size:10px;color:#92958b}.calendar-month{display:flex;align-items:center;justify-content:space-between;margin:16px 0 12px}.calendar-month strong{font-size:12px}.calendar-month button{background:none;color:#71796e;font-size:22px;width:26px;height:28px;border-radius:6px}.calendar-week,.calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));text-align:center;gap:6px 1px}.calendar-week{margin-bottom:10px;color:#9b9f97;font-size:10px}.calendar-grid button{position:relative;background:transparent;height:26px;width:26px;justify-self:center;border-radius:50%;font-size:11px;color:#586151;z-index:0;padding:0}.calendar-grid button:hover{background:#e7eadd}.calendar-grid button.has-interview:before{content:'';position:absolute;inset:3px;border:1.7px solid #d55250;border-radius:48% 52% 46% 54%;transform:rotate(-13deg);box-shadow:0 0 0 1px #d5525009}.calendar-grid button.selected{background:#d55250;color:#fff}.calendar-grid button.today:not(.selected){font-weight:700;color:#c44543}.calendar-legend{display:flex;align-items:center;justify-content:center;gap:6px;color:#919487;font-size:10px;margin-top:16px}.calendar-legend i{height:10px;width:10px;border:1.4px solid #d55250;border-radius:50%}.calendar-all{width:100%;background:none;font-size:11px;color:#767d6e;margin-top:14px;padding:6px}.calendar-message{font-size:11px;color:#8b665c;margin-top:12px}.calendar-message button{background:none;color:inherit;text-decoration:underline}.practice-calendar button:focus-visible{outline:2px solid #c84745;outline-offset:2px}@media(max-width:800px){.practice-calendar{max-width:310px;width:100%}}
</style>
<style scoped>
.calendar-grid button{width:clamp(26px,2vw,32px);height:clamp(26px,2vw,32px);font-size:12px}.calendar-heading h2{font-size:14px}.calendar-month strong{font-size:13px}
@media(max-width:960px){.practice-calendar{max-width:400px;margin:0 auto}.calendar-grid button{width:36px;height:36px}.calendar-month button{width:36px;height:36px}.calendar-all{min-height:40px}}
</style>
