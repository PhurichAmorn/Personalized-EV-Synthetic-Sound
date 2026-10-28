export function spectrumBins(frequencies: number[], levels: number[]): number[] {
  const bins = Array<number>(96).fill(0)
  for (let index = 0; index < Math.min(frequencies.length, levels.length); index++) {
    const frequency = frequencies[index]
    if (!Number.isFinite(frequency) || frequency < 0 || frequency > 2000) continue
    const bin = Math.min(95, Math.floor(frequency / 2000 * 96))
    bins[bin] = Math.max(bins[bin], Math.round(Math.max(0, Math.min(90, levels[index] + 90))))
  }
  return bins
}
