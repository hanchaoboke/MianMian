<template>
  <fieldset class="question-expression" :disabled="disabled">
    <legend>提问表达</legend>
    <div class="expression-heading">
      <label for="question-expression">口语化程度</label>
      <output for="question-expression">{{ selected.label }}</output>
    </div>
    <input id="question-expression" class="expression-range" type="range" min="1" max="5" step="1"
      :value="modelValue" :style="{ '--expression-progress': `${(modelValue - 1) * 25}%` }"
      :aria-valuetext="selected.label" aria-describedby="expression-example"
      @input="$emit('update:modelValue', Number($event.target.value))" />
    <div class="expression-scale" aria-hidden="true"><span>非常口语化</span><span>很专业</span></div>
    <div id="expression-example" class="expression-example">
      <span>表达示例</span><p>{{ selected.example }}</p>
    </div>
  </fieldset>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ modelValue: { type: Number, default: 3 }, disabled: Boolean })
defineEmits(['update:modelValue'])
const levels = [
  { label: '非常口语化', example: '你做的知识库问答，怎么判断它答得好不好？聊聊你会怎么测。' },
  { label: '轻松自然', example: '聊聊你的知识库问答项目，你会用哪些指标来判断回答质量？' },
  { label: '自然专业', example: '在你的 RAG 项目中，你会怎样设计评测指标来衡量回答质量？' },
  { label: '专业表达', example: '针对 RAG 系统的回答质量，你如何设计覆盖准确性与忠实性的评测指标？' },
  { label: '严谨专业', example: '针对 RAG 系统生成质量的验证，请阐述以答案准确性与上下文忠实性为核心的评测指标设计。' },
]
const selected = computed(() => levels[props.modelValue - 1] || levels[2])
</script>

<style scoped>
.question-expression { min-width: 0; margin: 2px 0 22px; padding: 18px 0 20px; border: 0; border-bottom: 1px solid #e5e9e7; }
.question-expression legend { padding: 0; color: #344f45; font-size: 14px; font-weight: 600; }
.expression-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.expression-heading label { color: #747e78; font-size: 13px; }
.expression-heading output { color: #277663; font-size: 13px; font-weight: 600; }
.expression-range { display: block; width: 100%; height: 32px; margin: 12px 0 0; padding: 0; appearance: none; background: transparent; cursor: pointer; }
.expression-range::-webkit-slider-runnable-track { height: 6px; border-radius: 3px; background: linear-gradient(to right, #377e6b 0 var(--expression-progress), #e2e8e4 var(--expression-progress) 100%); }
.expression-range::-moz-range-track { height: 6px; border-radius: 3px; background: #e2e8e4; }
.expression-range::-moz-range-progress { height: 6px; border-radius: 3px; background: #377e6b; }
.expression-range::-webkit-slider-thumb { width: 20px; height: 20px; margin-top: -7px; appearance: none; border: 3px solid #377e6b; border-radius: 50%; background: #fff; box-shadow: 0 1px 4px #264e4326; }
.expression-range::-moz-range-thumb { width: 14px; height: 14px; border: 3px solid #377e6b; border-radius: 50%; background: #fff; }
.expression-range:focus-visible { outline: 2px solid #377e6b; outline-offset: 3px; border-radius: 4px; }
.expression-range:disabled { cursor: default; opacity: 0.5; }
.expression-scale { display: flex; justify-content: space-between; gap: 16px; font-size: 12px; color: #8a948d; }
.expression-example { display: grid; grid-template-columns: 56px minmax(0, 1fr); align-items: start; align-content: start; gap: 14px; min-height: 66px; margin-top: 20px; }
.expression-example > span { padding-top: 2px; font-size: 12px; color: #8a948d; }
.expression-example p { margin: 0; padding-left: 14px; border-left: 2px solid #d1dfd8; color: #4b5e54; font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
@media (max-width: 650px) {
  .expression-example { grid-template-columns: minmax(0, 1fr); gap: 8px; min-height: 126px; }
}
</style>
