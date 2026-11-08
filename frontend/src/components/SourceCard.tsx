import { useState } from 'react'
import type { Source } from '../types'

type Props = { source: Source; rank: number }

/** Snippets are short previews, so flatten corpus LaTeX into readable text.
 *  The expanded full chunk stays verbatim for verification. */
function tidy(snippet: string): string {
  return snippet
    .replace(/\$\$([\s\S]*?)\$\$/g, (_m, body: string) => body.trim())
    .replace(/\\\[([\s\S]*?)\\\]/g, (_m, body: string) => body.trim())
    .replace(/\\text\{([^}]*)\}/g, '$1')
    .replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, '($1) / ($2)')
    .replace(/\\left|\\right/g, '')
    .replace(/\\\[|\\\]|\\\(|\\\)|\$\$/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function SourceCard({ source, rank }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <div className="source-card">
      <button className="source-head" onClick={() => setOpen(!open)} type="button">
        <span className="source-rank">{rank}</span>
        <span className="source-file" title={source.source}>{source.source}</span>
        <span className="source-score" title="Cosine similarity">
          {typeof source.semantic_score === 'number' ? source.semantic_score.toFixed(3) : '—'}
        </span>
        <span className="source-chevron">{open ? '−' : '+'}</span>
      </button>
      <p className="source-snippet">{tidy(source.snippet)}</p>
      {open && <pre className="source-full">{source.text}</pre>}
    </div>
  )
}
