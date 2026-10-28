import { useState } from 'react'
import type { ReactNode } from 'react'

type Props = {
  active: 'trace'
  onDashboard: () => void
  onTrace: () => void
  children: ReactNode
}

export default function PageShell({ active, onDashboard, onTrace, children }: Props) {
  const [expanded, setExpanded] = useState(false)
  return <div className="dashboard-screen">
    <aside className={'dashboard-rail' + (expanded ? ' expanded' : '')} aria-label="Main navigation">
      <button className="rail-button" title="Dashboard" aria-label="Dashboard" onClick={onDashboard}><img src="/icons/layout-dashboard.svg" alt="" /><span>DASHBOARD</span></button>
      <button className={'rail-button' + (active === 'trace' ? ' active' : '')} title="Sound trace" aria-label="Sound trace" onClick={onTrace}><img src="/icons/activity.svg" alt="" /><span>TRACE</span></button>
    </aside>
    <div className="dashboard-main">
      <header className="dashboard-header">
        <button className="header-sidebar" title="Toggle sidebar" aria-label="Toggle sidebar" onClick={() => setExpanded(!expanded)}><img src="/icons/panel-left.svg" alt="" /></button>
        <div className="dashboard-brand"><strong>EV SOUND LAB</strong><small>{active === 'trace' ? 'SOUND TRACE' : 'DIAGNOSTICS'}</small></div>
        <div className="header-spacer" />
        <span className="sound-caption">RESEARCH RECORDS</span>
      </header>
      <div className="dashboard-page">{children}</div>
    </div>
  </div>
}
