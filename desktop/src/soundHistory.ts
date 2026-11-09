import { BUILTIN_SOUND_PRESETS, DEFAULT_SOUND, type SoundConfig } from './soundAudition'
export type SoundHistory = { config: SoundConfig; presetId: string; past: { config: SoundConfig; presetId: string }[]; saved: string | null; group: number | null }
export type SoundAction =
  | { type: 'edit'; update: SoundConfig | ((current: SoundConfig) => SoundConfig); presetId: string; group: number | null }
  | { type: 'undo' }
  | { type: 'saved' }
export function initialSoundHistory(): SoundHistory {
  return { config: structuredClone(DEFAULT_SOUND), presetId: 'cinematic', past: [], saved: null, group: null }
}
export function soundSaveStatus(state: SoundHistory) {
  const current = JSON.stringify(state.config)
  if (current === state.saved) return 'Saved preset'
  const preset = BUILTIN_SOUND_PRESETS.find(preset => preset.id === state.presetId)
  return current === JSON.stringify(preset?.config) ? 'Preset unchanged' : 'Unsaved changes'
}
export function soundHistoryReducer(state: SoundHistory, action: SoundAction): SoundHistory {
  if (action.type === 'saved') return { ...state, saved: JSON.stringify(state.config) }
  if (action.type === 'undo') {
    const previous = state.past.at(-1)
    return previous ? { ...state, ...previous, past: state.past.slice(0, -1), group: null } : state
  }
  const config = typeof action.update === 'function' ? action.update(state.config) : action.update
  if (JSON.stringify(config) === JSON.stringify(state.config) && action.presetId === state.presetId) return state
  const grouped = action.group !== null && action.group === state.group
  return { ...state, config, presetId: action.presetId, past: grouped ? state.past : [...state.past.slice(-49), { config: state.config, presetId: state.presetId }], group: action.group }
}
