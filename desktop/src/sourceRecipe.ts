import { createSourceStems, SOURCE_FAMILIES, type SourceFamily, type SourceShape, type SourceControls } from './sourceDesigner'
export const RECIPE_DEFAULT_CONTROLS: SourceControls = { body: .7, character: .5, ensemble: .65, movement: .5 }
export type SourceLayer = { role: 'foundation' | 'character' | 'texture'; method: SourceFamily; gain: number; shape: SourceShape; controls?: SourceControls }
export type SourceRecipe = { version: 1; seed: number; layers: SourceLayer[] }
export function validateRecipe(recipe: SourceRecipe) {
  if (recipe.version !== 1 || !Number.isSafeInteger(recipe.seed) || recipe.seed < 0 || !Array.isArray(recipe.layers) || recipe.layers.length < 1 || recipe.layers.length > 3) throw Error('Invalid source recipe')
  const roles = new Set<string>()
  for (const [index, layer] of recipe.layers.entries()) {
    if (!['foundation', 'character', 'texture'].includes(layer.role) || roles.has(layer.role) || (index === 0 && layer.role !== 'foundation') || !SOURCE_FAMILIES.some(item => item.id === layer.method) || !Number.isFinite(layer.gain) || layer.gain <= 0 || layer.gain > (index === 0 ? 1 : .65) || !layer.shape || typeof layer.shape !== 'object') throw Error('Invalid recipe layer')
    if (layer.controls && (Object.keys(layer.controls).length !== 4 || Object.entries(layer.controls).some(([key, value]) => !(key in RECIPE_DEFAULT_CONTROLS) || !Number.isFinite(value) || value < 0 || value > 1))) throw Error('Invalid recipe source controls')
    roles.add(layer.role)
  }
}
export function renderRecipe(recipe: SourceRecipe, rate = 48000) {
  validateRecipe(recipe)
  const output = Array.from({ length: 3 }, () => [new Float32Array(rate * 5), new Float32Array(rate * 5)])
  for (const [index, layer] of recipe.layers.entries()) {
    const phase = recipe.seed === 0 ? 0 : ((recipe.seed + index * 131) % 997) / 997 * 2 * Math.PI
    const stems = createSourceStems(layer.controls ?? RECIPE_DEFAULT_CONTROLS, rate, layer.method, { ...layer.shape, seedPhase: phase })
    for (let s = 0; s < 3; s++) for (let c = 0; c < 2; c++) for (let i = 0; i < rate * 5; i++) output[s][c][i] += stems[s][c][i] * layer.gain
  }
  let energy = 0, peak = 0
  for (let c = 0; c < 2; c++) for (let i = 0; i < rate * 5; i++) {
    const sample = output[0][c][i] + output[1][c][i] + output[2][c][i]
    energy += sample * sample; peak = Math.max(peak, Math.abs(sample))
  }
  const scale = Math.min(.13 / Math.sqrt(energy / (rate * 10)), .7 / Math.max(peak, 1e-10))
  for (const stem of output) for (const channel of stem) for (let i = 0; i < channel.length; i++) channel[i] *= scale
  return output
}
