import { Menu, ShieldCheck, TriangleAlert } from 'lucide-react'
import type { View } from '../types'

type Props = {
  view: View
  onOpenMobileNav: () => void
  online: boolean
  configured: boolean
  model: string
}

const TITLES: Record<View, { title: string; subtitle: string }> = {
  home: { title: 'Overview', subtitle: 'Your document intelligence workspace' },
  chat: { title: 'Chat with Documents', subtitle: 'Ask anything about your indexed sources' },
  upload: { title: 'Upload Documents', subtitle: 'Add new sources to your knowledge base' },
  library: { title: 'Document Library', subtitle: 'Files currently available for retrieval' },
  settings: { title: 'Settings', subtitle: 'Connection, retrieval and system information' },
}

export function TopBar({ view, onOpenMobileNav, online, configured, model }: Props) {
  const { title, subtitle } = TITLES[view]
  const ready = online && configured

  return (
    <header className="topbar">
      <button className="icon-btn mobile-only menu-btn" aria-label="Open navigation"
        onClick={onOpenMobileNav}><Menu size={20} /></button>
      <div className="topbar-titles">
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <span className={`status-pill ${ready ? 'ready' : 'attention'}`}>
          {ready ? <ShieldCheck size={14} /> : <TriangleAlert size={14} />}
          {!online ? 'Backend offline' : configured ? 'Ready' : 'Setup needed'}
        </span>
        {model && <span className="model-pill" title="Active generation model">{model}</span>}
      </div>
    </header>
  )
}
