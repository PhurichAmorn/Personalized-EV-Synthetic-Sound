// Renders every labelled sound with the app's own synth, writes manifest.json + one mono float32 file per sound.
import { writeFileSync, mkdirSync } from 'node:fs'
import { STARTING_SOUNDS, VARIANTS, SEARCH_FIXED } from '../../desktop/src/levels'
import { EXTRAS_OFF, createPlainSource, plainPartials, type PlainParams } from '../../desktop/src/plainSource'

const full = (p: Partial<PlainParams>): PlainParams => ({ ...EXTRAS_OFF, rootHz: 175, brightness: .5, hollow: 0, bell: 0, air: 0, softTop: 1800, chord: 0, ...p })
const SPACE = { small: { chorus: 1, reverb: .25, size: 1.2 }, large: { chorus: 2, reverb: .4, size: 2.5 } }
const motion = (space: 'small' | 'large', vibrato: boolean, tremolo: boolean) => ({ ...SEARCH_FIXED, ...SPACE[space], tone: 2000, follow: 1, bodyDb: 0, vibDepth: vibrato ? 6 : 0, tremDepth: tremolo ? .2 : 0 })

type Item = { id: string; name: string; label: 'ok' | 'unpleasant'; why: string; plain: Partial<PlainParams>; fx: object }
const items: Item[] = []
// Current faces and variants: all Keep at the last listen (some "similar", none unpleasant).
for (const s of [...STARTING_SOUNDS, ...Object.values(VARIANTS).flat()])
  if (!items.some(i => i.id === s.id)) items.push({ id: s.id, name: s.name, label: 'ok', why: 'Keep', plain: { width: 1, ...s.plain }, fx: s.fx })
// Retired but kept by ear (dropped for similarity or boredom, not for being unpleasant).
items.push(
  { id: 'pure', name: 'Pure tone', label: 'ok', why: 'Maybe: basic', plain: { rootHz: 196, brightness: .15, softTop: 3000, chord: .35, chordType: 3 }, fx: { ...motion('large', true, false), tone: 6000 } },
  { id: 'turbine', name: 'Turbine', label: 'ok', why: 'Keep', plain: { rootHz: 110, whine: .7, whineRatio: 4.5, fundamental: .5, brightness: .5, softTop: 900, chord: .6, chordType: 2 }, fx: motion('small', false, true) },
  { id: 'digital', name: 'Digital (final)', label: 'ok', why: 'Keep', plain: { rootHz: 196, hollow: .7, brightness: .3, softTop: 1200, chord: .7, chordType: 2, bell: .9 }, fx: motion('large', false, false) },
  { id: 'night', name: 'Night drive', label: 'ok', why: 'Keep', plain: { rootHz: 175, brightness: .7, hollow: .15, softTop: 3000, chord: 1, chordType: 2, detune: .7 }, fx: { ...motion('large', false, false), tone: 1500, res: 8, pump: 1, tremRate: 1.75, tremDepth: .25 } },
)
// Sounds the listener called unpleasant (settings recovered from the session's edit history).
items.push(
  { id: 'growl', name: 'Growl', label: 'unpleasant', why: 'Drop: very uncomfortable', plain: { rootHz: 98, brightness: 1, hollow: .4, softTop: 6000, chord: 0 }, fx: { ...motion('small', false, false), tone: 6000 } },
  { id: 'sweep', name: 'Sci-fi sweep', label: 'unpleasant', why: 'Drop: very uncomfortable, too high', plain: { rootHz: 110, brightness: .95, softTop: 6000, chord: .5, chordType: 3, detune: .3 }, fx: { ...motion('large', false, false), tone: 1800, res: 10, drift: 1, driftPeriod: 4 } },
  { id: 'digital-v1', name: 'Digital (first)', label: 'unpleasant', why: 'Maybe: too irritating', plain: { rootHz: 196, hollow: .95, brightness: .6, softTop: 2000, chord: 0 }, fx: motion('large', false, false) },
  { id: 'whine-v1', name: 'Electric whine 7.5x', label: 'unpleasant', why: 'Maybe: too high, uncomfortable for ears', plain: { rootHz: 98, fundamental: .6, brightness: .25, softTop: 700, chord: 0, whine: 1, whineRatio: 7.5 }, fx: { ...motion('small', false, false), tone: 6000 } },
  { id: 'pulse-v1', name: 'Pulse', label: 'unpleasant', why: 'Maybe: pulse too much, very weird', plain: { rootHz: 165, brightness: .55, hollow: .5, softTop: 2000, chord: .6, chordType: 3 }, fx: { ...motion('large', false, false), tone: 3000, pump: 1, tremDepth: .9, tremRate: 4 } },
)
mkdirSync('audio', { recursive: true })
const manifest = items.map(item => {
  const plain = full(item.plain)
  writeFileSync(`audio/${item.id}.f32`, Buffer.from(createPlainSource(plain)[0].buffer))
  return { ...item, plain, partials: plainPartials(plain).map(({ hz, amp }) => [hz, amp]) }
})
writeFileSync('manifest.json', JSON.stringify(manifest))
console.log(manifest.length, 'sounds')
