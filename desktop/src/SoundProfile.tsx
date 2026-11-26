import { useT } from './i18n'

/** Plain-language sound profile: one row per trait, a dot between two everyday words. Shared by the final-sound screen and the Trace page
 * (so the dashboard and the BeamNG overlay always show the same thing). Reads the building-block settings (experiment/sound_blocks.py);
 * a sound without them (older searches) shows nothing. */
type Blocks = { pitch?: number; brightness?: number; level?: string; space?: string; buzz?: number; top?: string }
const PITCH_STEPS = 4      // PITCHES in sound_blocks.py has five steps, 47-119 Hz
const LEVEL = { soft: 0, medium: 0.5, strong: 1 } as Record<string, number>

const blocksOf = (recipe: unknown): Blocks | null => (recipe as { blocks?: Blocks } | null)?.blocks ?? null
export const hasProfile = (recipe: unknown) => !!blocksOf(recipe)

/** Rows as [low word, high word, position 0..1]. Buzz only when the sound has a synth top (it is meaningless for the others). */
export function profileRows(recipe: unknown): [string, string, number][] {
  const b = blocksOf(recipe)
  if (!b) return []
  const rows: [string, string, number][] = []
  if (typeof b.pitch === 'number') rows.push(['Deep', 'High', b.pitch / PITCH_STEPS])
  if (typeof b.brightness === 'number') rows.push(['Dark', 'Bright', b.brightness])
  if (b.level && b.level in LEVEL) rows.push(['Soft', 'Strong', LEVEL[b.level]])
  if (b.space) rows.push(['Up close', 'Spacious', b.space === 'dry' ? 0 : 1])
  if ((b.top === 'synth' || b.top === 'bell') && typeof b.buzz === 'number') rows.push(['Smooth', 'Buzzy', b.buzz / 2])
  return rows
}

export default function SoundProfile({ recipe, title }: { recipe: unknown; title?: string }) {
  const t = useT(), rows = profileRows(recipe)
  if (!rows.length) return null
  return <div className="sound-profile" role="group" aria-label={t(title ?? 'Sound profile')}>
    {rows.map(([low, high, at]) => <div className="sound-profile-row" key={low}>
      <span>{t(low)}</span>
      <i role="img" aria-label={`${t(low)} – ${t(high)}: ${Math.round(at * 100)}%`}><b style={{ left: `${Math.round(at * 100)}%` }} /></i>
      <span>{t(high)}</span>
    </div>)}
  </div>
}
