import { useState } from 'react'
import type { ReactNode } from 'react'
import NavRail, { type NavTarget } from './NavRail'

export default function PageShell({ active, title, onNavigate, children }: { active: NavTarget; title: string; onNavigate: (target: NavTarget) => void; children: ReactNode }) {
  const [expanded, setExpanded] = useState(false)
  return <div className="dashboard-screen">
    <NavRail active={active} expanded={expanded} onSelect={onNavigate} />
    <div className="dashboard-main">
      <header className="dashboard-header">
        <button className="header-sidebar" title="Toggle sidebar" aria-label="Toggle sidebar" onClick={() => setExpanded(!expanded)}><img src="/icons/panel-left.svg" alt="" /></button>
        <div className="dashboard-brand"><strong>EV SOUND LAB</strong><small>{title}</small></div>
        <div className="header-spacer" />
        <span className="sound-caption">RESEARCH RECORDS</span>
      </header>
      <div className="dashboard-page">{children}</div>
    </div>
  </div>
}
