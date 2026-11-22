import { useState } from 'react'
import type { ReactNode } from 'react'
import NavRail, { type NavTarget } from './NavRail'
import { useT } from './i18n'

/** The app's brand, one place for every page header (dashboard and research pages). */
export function Brand({ sub }: { sub: string }) {
  const t = useT()
  return <div className="dashboard-brand"><strong>{t('EV SOUND LAB')}</strong><small>{t(sub)}</small></div>
}

export default function PageShell({ active, title, onNavigate, children }: { active: NavTarget; title: string; onNavigate: (target: NavTarget) => void; children: ReactNode }) {
  const t = useT()
  const [expanded, setExpanded] = useState(false)
  return <div className="dashboard-screen">
    <NavRail active={active} expanded={expanded} onSelect={onNavigate} />
    <div className="dashboard-main">
      <header className="dashboard-header">
        <button className="header-sidebar" title={t('Toggle sidebar')} aria-label={t('Toggle sidebar')} onClick={() => setExpanded(!expanded)}><img src="/icons/panel-left.svg" alt="" /></button>
        <Brand sub={title} />
        <div className="header-spacer" />
        <span className="sound-caption">{t('RESEARCH RECORDS')}</span>
      </header>
      <div className="dashboard-page">{children}</div>
    </div>
  </div>
}
