/** Builds plain-source stems off the main thread (0.1-0.5 s per sound; on the main thread it froze the UI on every A/B switch). */
import { createPlainVoices, type PlainParams } from './plainSource'
self.onmessage = (event: MessageEvent<{ id: number; plain: PlainParams }>) => {
  const { id, plain } = event.data
  try {
    const voices = createPlainVoices(plain)
    self.postMessage({ id, voices }, { transfer: voices.flat().map(channel => channel.buffer) })
  } catch (problem) { self.postMessage({ id, error: problem instanceof Error ? problem.message : String(problem) }) }
}
