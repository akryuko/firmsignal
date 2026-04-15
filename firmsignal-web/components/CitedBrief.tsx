"use client"

import ReactMarkdown from "react-markdown"
import { Source } from "@/types"

interface Props {
  brief:   string
  sources: Source[]
}

function buildIndex(sources: Source[]): Map<number, string> {
  const index = new Map<number, string>()
  const seen  = new Set<string>()
  let n = 1
  for (const s of sources) {
    if (s.url && !seen.has(s.url)) {
      seen.add(s.url)
      index.set(n, s.url)
      n++
    }
  }
  return index
}

function makeClickable(brief: string, index: Map<number, string>): string {
  return brief.replace(/\[(\d+)\]/g, (match, num) => {
    const url = index.get(parseInt(num))
    return url ? `[[${num}]](${url})` : match
  })
}

// Detect citation links: link text is exactly "[N]"
function isCitation(text: React.ReactNode): boolean {
  const str = String(text)
  return /^\[\d+\]$/.test(str)
}

export function CitedBrief({ brief, sources }: Props) {
  const index     = buildIndex(sources)
  const clickable = makeClickable(brief, index)

  return (
    <div className="prose prose-slate max-w-none
      prose-headings:font-semibold prose-headings:text-slate-800
      prose-p:text-slate-700 prose-p:leading-relaxed prose-p:text-sm
      prose-a:no-underline hover:prose-a:underline
      prose-li:text-slate-700 prose-li:text-sm
      prose-strong:text-slate-800 prose-strong:font-semibold
      prose-blockquote:border-l-emerald-400 prose-blockquote:text-slate-600">
      <ReactMarkdown
        components={{
          // Section headers — visual separator above each h2
          h2: ({ children }) => (
            <h2 className="mt-8 border-t border-slate-100 pt-6 text-base font-semibold text-slate-800 first:mt-0 first:border-t-0 first:pt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
              {children}
            </h3>
          ),
          // Paragraphs — tighter spacing inside sections
          p: ({ children }) => (
            <p className="mt-3 text-sm leading-relaxed text-slate-700">
              {children}
            </p>
          ),
          // Lists
          ul: ({ children }) => (
            <ul className="mt-3 space-y-1 pl-4">{children}</ul>
          ),
          li: ({ children }) => (
            <li className="text-sm leading-relaxed text-slate-700">{children}</li>
          ),
          // Bold — used for "Bull case:" / "Bear case:" labels
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-800">{children}</strong>
          ),
          // Links — citations render as superscript, regular links as emerald text
          a: ({ href, children }) => {
            if (isCitation(children)) {
              const num = String(children).replace(/\[|\]/g, "")
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="relative -top-0.5 ml-0.5 text-[10px] font-medium text-emerald-600 hover:underline"
                >
                  {num}
                </a>
              )
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-600 hover:underline"
              >
                {children}
              </a>
            )
          },
          // Horizontal rules between major blocks
          hr: () => <hr className="my-6 border-slate-100" />,
        }}
      >
        {clickable}
      </ReactMarkdown>
    </div>
  )
}