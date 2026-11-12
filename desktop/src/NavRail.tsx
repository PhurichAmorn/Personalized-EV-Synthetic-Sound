export type NavTarget = 'dashboard' | 'trace' | 'soundlab'
const items: { target: NavTarget; title: string; label: string; icon: string }[] = [
  { target: 'dashboard', title: 'Dashboard', label: 'DASHBOARD', icon: 'layout-dashboard' },
  { target: 'trace', title: 'Sound trace', label: 'TRACE', icon: 'activity' },
  { target: 'soundlab', title: 'Sound Lab', label: 'SOUND LAB', icon: 'sliders' },
]
// The one main-navigation rail, shared by every page. Add a page here and it appears everywhere.
export default function NavRail({ active, expanded, onSelect }: { active: NavTarget; expanded: boolean; onSelect: (target: NavTarget) => void }) {
  return <aside className={'dashboard-rail' + (expanded ? ' expanded' : '')} aria-label="Main navigation">
    {items.map(item => <button key={item.target} className={'rail-button' + (active === item.target ? ' active' : '')} title={item.title} aria-label={item.title} onClick={() => onSelect(item.target)}><img src={`/icons/${item.icon}.svg`} alt="" /><span>{item.label}</span></button>)}
  </aside>
}
