import type { PlainParams } from './plainSource'
import type { MapVoice } from './mapVoice'
import { isMapRecipe, liveSound, type LiveRecipe } from './levels'

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
export const plainVoices = (plain: PlainParams) => build({ plain })
const message = (recipe: LiveRecipe) => isMapRecipe(recipe) && recipe.voice ? { voice: recipe.voice } : { plain: liveSound(recipe).plain }
/** Stems of any live-built search sound: plain synth settings, or a sound-map voice (plain, blocks or stack). */
export const liveStems = (recipe: LiveRecipe) => build(message(recipe))
/** The driver's own sound (GS, BeamNG): also saved on disk, so after its first build it loads at app start without building again
 * (a layered sound takes 1-5 s and a CPU burst, not wanted while BeamNG runs). One sound is kept; a new own sound replaces it. */
export function ownStems(recipe: LiveRecipe) { own = JSON.stringify(message(recipe)); return liveStems(recipe) }
let own = ''

function build(message: { plain: PlainParams } | { voice: MapVoice }) {
  const key = JSON.stringify(message)
  let voices = cache.get(key)
  if (!voices) {
    voices = key === own ? stored(key).then(saved => saved ?? fresh(message).then(built => { void store(key, built); return built })) : fresh(message)
    voices.catch(() => cache.delete(key))
    cache.set(key, voices)
    if (cache.size > LIMIT) cache.delete(cache.keys().next().value!)
  }
  return voices
}
function fresh(message: { plain: PlainParams } | { voice: MapVoice }) {
  const id = next++
  const voices = new Promise<Float32Array[][]>((resolve, reject) => waiting.set(id, { resolve, reject }))
  if (!worker) { worker = new Worker(new URL('./voiceWorker.ts', import.meta.url), { type: 'module' }); worker.onmessage = onMessage }
  worker.postMessage({ id, ...message })
  return voices
}

// On disk: IndexedDB in the app's webview profile (persists across restarts). Any failure just means building again.
const STORE = 'stems'
const database = () => new Promise<IDBDatabase>((resolve, reject) => {
  const request = indexedDB.open('ev-own-sound', 1)
  request.onupgradeneeded = () => request.result.createObjectStore(STORE)
  request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error)
})
async function stored(key: string): Promise<Float32Array[][] | undefined> {
  try {
    const db = await database()
    return await new Promise(resolve => { const get = db.transaction(STORE).objectStore(STORE).get(key); get.onsuccess = () => resolve(get.result); get.onerror = () => resolve(undefined) })
  } catch { return undefined }
}
async function store(key: string, voices: Float32Array[][]) {
  try { const items = (await database()).transaction(STORE, 'readwrite').objectStore(STORE); items.clear(); items.put(voices, key) } catch { /* not saved: built again next time */ }
}
