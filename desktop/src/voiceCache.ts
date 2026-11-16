import type { PlainParams } from './plainSource'

/** Stems built in a worker and kept per sound, so switching A/B (or back) does not rebuild them. */
// Worker starts on the first build, not at app load.
let worker: Worker | null = null
const cache = new Map<string, Promise<Float32Array[][]>>()
const waiting = new Map<number, { resolve: (voices: Float32Array[][]) => void; reject: (error: Error) => void }>()
let next = 0
const onMessage = (event: MessageEvent<{ id: number; voices?: Float32Array[][]; error?: string }>) => {
  const { id, voices, error } = event.data, job = waiting.get(id)
  waiting.delete(id)
  if (voices) job?.resolve(voices); else job?.reject(new Error(error ?? 'Sound build failed'))
}
const LIMIT = 24  // about 2 MB per sound
export function plainVoices(plain: PlainParams) {
  const key = JSON.stringify(plain)
  let voices = cache.get(key)
  if (!voices) {
    const id = next++
    voices = new Promise((resolve, reject) => waiting.set(id, { resolve, reject }))
    voices.catch(() => cache.delete(key))
    if (!worker) { worker = new Worker(new URL('./voiceWorker.ts', import.meta.url), { type: 'module' }); worker.onmessage = onMessage }
    worker.postMessage({ id, plain })
    cache.set(key, voices)
    if (cache.size > LIMIT) cache.delete(cache.keys().next().value!)
  }
  return voices
}
