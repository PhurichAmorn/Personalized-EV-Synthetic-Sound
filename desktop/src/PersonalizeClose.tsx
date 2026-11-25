import { createContext, useContext } from 'react'
import { useT } from './i18n'

/** The X that leaves Personalize. App provides what it does (pause/end prompt or leave); the session panel draws it in its own top right corner. */
export const PersonalizeCloseContext = createContext<(() => void) | null>(null)

export function PersonalizeCloseButton() {
  const t = useT(), close = useContext(PersonalizeCloseContext)
  if (!close) return null
  return <button type="button" className="control search-close" aria-label={t('Close')} title={t('Close')} onClick={close}><svg className="x-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4L20 20M20 4L4 20" /></svg></button>
}
