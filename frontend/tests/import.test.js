import test from 'node:test'
import assert from 'node:assert/strict'
import { importQuestions } from '../src/api.js'

test('stream decoder preserves split Chinese UTF-8, progress and complete draft', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => {
    const bytes = new TextEncoder().encode([
      JSON.stringify({type:'progress', completed:1, total:41, questions:1}),
      JSON.stringify({type:'complete', draft:{questions:[{question:'如何设计系统？'}]}}),
    ].join('\n') + '\n')
    return new Response(new ReadableStream({start(controller) {
      for (let i=0; i<bytes.length; i+=7) controller.enqueue(bytes.slice(i,i+7))
      controller.close()
    }}))
  })
  globalThis.localStorage = {getItem: () => null}
  const events = []
  const draft = await importQuestions(new FormData(), e => events.push(e))
  assert.equal(draft.questions[0].question, '如何设计系统？')
  assert.equal(events[0].total, 41)
})

test('stream failure or premature close never becomes successful import', async (t) => {
  globalThis.localStorage = {getItem: () => null}
  const response = t.mock.method(globalThis, 'fetch', async () => new Response('{"type":"progress","completed":1}\n'))
  await assert.rejects(importQuestions(new FormData(), () => {}), /连接中断/)
  response.mock.mockImplementation(async () => new Response('{"type":"error","message":"模型失败"}\n'))
  await assert.rejects(importQuestions(new FormData(), () => {}), /模型失败/)
  response.mock.mockImplementation(async () => new Response('{"detail":"没有访问权限"}', {status:403}))
  await assert.rejects(importQuestions(new FormData(), () => {}), /没有访问权限/)
})
