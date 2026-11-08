import {
  BookOpen, House, MessageSquareText, PanelLeftClose, PanelLeftOpen,
  Settings2, Sparkles, UploadCloud, X,
} from 'lucide-react'
import type { View } from '../types'

type Props = {
  view: View
  onNavigate: (view: View) => void
  collapsed: boolean
  onToggleCollapse: () => void
  mobileOpen: boolean
  onCloseMobile: () => void
  online: boolean
  documentCount: number
}

const NAV: { id: View; label: string; icon: typeof House; hint: string }[] = [
  { id: 'home', label: 'Home', icon: House, hint: 'Overview' },
  { id: 'chat', label: 'Chat with Documents', icon: MessageSquareText, hint: 'Ask questions' },
  { id: 'upload', label: 'Upload Documents', icon: UploadCloud, hint: 'Add sources' },
  { id: 'library', label: 'Document Library', icon: BookOpen, hint: 'Manage sources' },
  { id: 'settings', label: 'Settings', icon: Settings2, hint: 'Preferences' },
]

export function Sidebar({ view, onNavigate, collapsed, onToggleCollapse,
  mobileOpen, onCloseMobile, online, documentCount }: Props) {
  const go = (id: View) => { onNavigate(id); onCloseMobile() }
  // A mobile drawer is always expanded, even if the desktop rail is collapsed.
  const compact = collapsed && !mobileOpen

  return (
    <>
      {mobileOpen && <button className="sidebar-scrim" aria-label="Close navigation"
        onClick={onCloseMobile} />}
      <aside className={`sidebar ${compact ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true"><Sparkles size={18} strokeWidth={2.1} /></div>
          {!compact && (
            <div className="brand-text">
              <strong>Lumen</strong>
              <span>Document Intelligence</span>
            </div>
          )}
          <button className="icon-btn mobile-only" aria-label="Close navigation"
            onClick={onCloseMobile}><X size={18} /></button>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {!compact && <div className="nav-caption">Workspace</div>}
          {NAV.map(({ id, label, icon: Icon, hint }) => (
            <button key={id} type="button"
              className={`nav-item ${view === id ? 'active' : ''}`}
              onClick={() => go(id)} title={compact ? label : hint}
              aria-current={view === id ? 'page' : undefined}>
              <Icon size={18} strokeWidth={1.9} />
              {!compact && <span className="nav-label">{label}</span>}
              {!compact && id === 'library' && (
                <span className="nav-count">{documentCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          {!compact && (
            <div className="sidebar-status">
              <span className={`status-dot ${online ? 'ok' : 'off'}`} />
              <div>
                <strong>{online ? 'System ready' : 'Backend offline'}</strong>
                <span>{documentCount} documents indexed</span>
              </div>
            </div>
          )}
          <button className="collapse-btn" type="button" onClick={onToggleCollapse}
            title={compact ? 'Expand sidebar' : 'Collapse sidebar'}>
            {compact ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
            {!compact && <span>Collapse</span>}
          </button>
        </div>
      </aside>
    </>
  )
}
