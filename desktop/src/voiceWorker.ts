/** Builds source stems off the main thread (0.1-1 s per sound; on the main thread it froze the UI on every A/B switch).
 * Plain synth settings, or a sound-map voice (plain or blocks). */
import { createPlainVoices, type PlainParams } from './plainSource'
import { mapStems, type MapVoice } from './mapVoice'
self.onmessage = (event: MessageEvent<{ id: number; plain?: PlainParams; voice?: MapVoice }>) => {
  const { id, plain, voice } = event.data
  try {
    const voices = voice ? mapStems(voice) : createPlainVoices(plain!)
    self.postMessage({ id, voices }, { transfer: voices.flat().map(channel => channel.buffer) })
  } catch (problem) { self.postMessage({ id, error: problem instanceof Error ? problem.message : String(problem) }) }
}
