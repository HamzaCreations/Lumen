import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import type { Source } from '../types'

type Props = {
  text: string
  /** Rich rendering is enabled once the SSE stream has finished. */
  rich: boolean
  sources?: Source[]
}

const katexOptions = {
  throwOnError: false,
  strict: 'ignore' as const,
  output: 'html' as const,
}

/** Convert model quirks into clean Markdown before rendering. */
function normalize(raw: string): string {
  let s = raw.replace(/\r\n/g, '\n')

  // LaTeX display/inline delimiters -> what remark-math understands.
  s = s.replace(/\\\[([\s\S]*?)\\\]/g, (_m, body: string) => `\n$$\n${body.trim()}\n$$\n`)
  s = s.replace(/\\\(([\s\S]*?)\\\)/g, (_m, body: string) => `$${body.trim()}$`)
  s = s.replace(/\\\[|\\\]/g, '').replace(/\\\(|\\\)/g, '')

  // 【Source 1: file.txt】 / [Source 1: file.txt] / [Source 1] -> compact chip links.
  // A fragment URL survives react-markdown's protocol sanitizer.
  s = s.replace(/【\s*Source\s*(\d+)\s*(?::\s*[^】]+)?】/g, (_m, n) => `[${n}](#cite-${n})`)
  s = s.replace(/【\s*(\d+)\s*】/g, (_m, n) => `[${n}](#cite-${n})`)
  s = s.replace(/\[Source\s*(\d+)\s*(?::\s*[^\]]+)?\]/g, (_m, n) => `[${n}](#cite-${n})`)

  return s
}

/** Plain-text fallback used while tokens are still arriving. */
function plain(raw: string): string {
  return raw
    .replace(/\\\[|\\\]|\\\(|\\\)/g, '')
    .replace(/【\s*Source\s*(\d+)\s*(?::[^】]+)?】/g, '[$1]')
    .replace(/【\s*(\d+)\s*】/g, '[$1]')
    .replace(/\[Source\s*(\d+)\s*(?::[^\]]+)?\]/g, '[$1]')
}

export function AnswerText({ text, rich, sources }: Props) {
  if (!rich) return <span className="plain-answer">{plain(text)}</span>

  const components: Components = {
    a: ({ href, children, node, ...rest }) => {
      void node
      if (href?.startsWith('#cite-')) {
        const n = Number(href.slice(6))
        const file = sources?.[n - 1]?.source
        return (
          <button type="button" className="cite-chip"
            title={file ? `Source ${n}: ${file} — click to jump` : `Source ${n}`}
            onClick={(e) => {
              const cards = e.currentTarget.closest('.message')?.querySelectorAll('.source-card')
              cards?.[n - 1]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }}>
            {children}
          </button>
        )
      }
      return <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>{children}</a>
    },
  }

  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, katexOptions]]}
        components={components}
      >
        {normalize(text)}
      </ReactMarkdown>
    </div>
  )
}
