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

export function CitedBrief({ brief, sources }: Props) {
  const index     = buildIndex(sources)
  const clickable = makeClickable(brief, index)

  return (
    <div className="prose prose-slate prose-sm max-w-none
      prose-headings:font-semibold prose-headings:text-slate-800
      prose-p:text-slate-700 prose-p:leading-relaxed
      prose-a:text-emerald-600 prose-a:no-underline
      hover:prose-a:underline
      prose-li:text-slate-700
      prose-strong:text-slate-800
      prose-blockquote:border-l-emerald-400">
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-600 hover:underline"
            >
              {children}
            </a>
          ),
        }}
      >
        {clickable}
      </ReactMarkdown>
    </div>
  )
}