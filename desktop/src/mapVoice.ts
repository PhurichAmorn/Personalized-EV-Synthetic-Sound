import { createPlainVoices, EXTRAS_OFF, type PlainParams } from './plainSource'
import { renderRecipe } from './sourceRecipe'
import type { SourceControls, SourceShape } from './sourceDesigner'
import { stackStems, stackStage, type StackParams, type StackTrend } from './stackVoice'

/** The source of a sound-map sound (tools/sound_map, SoundMapDiscovery): the plain synth (plainSource.ts) or the generic
 * 'blocks' voice (sourceDesigner.ts: harmonic slope, resonant peaks, FM, noise band, waveshaper, amplitude modulation, inharmonic
 * partials). Both give three stereo stems for the granular players. Source movement is fixed at 0 for blocks: its vibrato would be
 * baked into the loop and turn into a level wobble once transposed (vibrato belongs in the engine). */
export type MapVoice = { kind: 'plain'; plain: Partial<PlainParams> } | { kind: 'blocks'; shape: SourceShape; controls: SourceControls } | { kind: 'stack'; stack: StackParams }

export function mapStems(voice: MapVoice): Float32Array[][] {
  if (voice.kind === 'stack') return stackStems(voice.stack)
  if (voice.kind === 'blocks') return renderRecipe({ version: 1, seed: 0, layers: [{ role: 'foundation', method: 'blocks', gain: 1, shape: voice.shape, controls: { ...voice.controls, movement: 0 } }] })
  return createPlainVoices({ ...EXTRAS_OFF, air: 0, ...voice.plain } as PlainParams)
}

/** Main note of the loop in Hz (blocks: 174.8 Hz x rootRatio on the 0.2 Hz loop grid, as createSourceStems). */
export const mapRootHz = (voice: MapVoice) => voice.kind === 'stack' ? voice.stack.rootHz : voice.kind === 'blocks' ? Math.round(174.8 * (voice.shape.rootRatio ?? 1) * 5) / 5 : voice.plain.rootHz ?? 175
/** Fixed after-player stage of a voice ('stack' only), applied by the granular players. */
export const mapStage = (voice: MapVoice) => voice.kind === 'stack' ? stackStage(voice.stack) : undefined
/** Per-player drive trends of a voice ('stack' with roles only). */
export const mapTrend = (voice: MapVoice): StackTrend | undefined => voice.kind === 'stack' ? voice.stack.trend : undefined
