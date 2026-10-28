import assert from 'node:assert/strict'
import test from 'node:test'
import { createClient } from './client.ts'

test('commands resolve only for their matching reply and pass state events', async () => {
  let receive: (message: string) => void = () => {}
  const sent: string[] = []
  const client = createClient(async message => { sent.push(message) }, async handler => {
    receive = handler
    return () => {}
  })
  const states: unknown[] = []
  await client.connect(message => { if (message.event === 'state') states.push(message.data) })
  const first = client.command('snapshot', {})
  const second = client.command('vehicle', { name: 'Compact EV' })
  assert.equal(JSON.parse(sent[0]).id, 1)
  assert.equal(JSON.parse(sent[1]).id, 2)
  receive(JSON.stringify({ event: 'state', data: { speed: 0 } }))
  receive(JSON.stringify({ id: 2, result: { vehicle: 'Compact EV' } }))
  receive(JSON.stringify({ id: 1, result: { speed: 0 } }))
  assert.deepEqual(await first, { speed: 0 })
  assert.deepEqual(await second, { vehicle: 'Compact EV' })
  assert.deepEqual(states, [{ speed: 0 }])
})
