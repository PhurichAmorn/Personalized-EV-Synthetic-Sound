/** Fixed manual gesture for auditioning source response, independent of vehicle inputs. */
export function climbTargets(value: number) {
  const x = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0))
  const rise = x * x * (3 - 2 * x)
  return {
    semitones: 5 * rise,
    rate: Math.pow(2, 5 * rise / 12),
    bodyGain: 1 - .2 * rise,
    padGain: 1 + .15 * rise,
    glassGain: .6 + .8 * rise,
    airGain: 1,
    cutoff: 1600 + 2400 * rise,
  }
}
