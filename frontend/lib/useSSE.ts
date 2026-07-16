"use client"

import { useEffect, useRef } from "react"
import { getStreamUrl } from "@/lib/api"
import { useRunStore } from "@/store/run"
import { HitlPayload, Source } from "@/types"

export function useSSE(runId: string | null) {
  const store = useRunStore()
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!runId) return

    esRef.current?.close()

    const es = new EventSource(getStreamUrl(runId))
    esRef.current = es

    es.addEventListener("correction", (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      store.setCorrection(data.resolved, data.note)
    })

    es.addEventListener("agent_start", (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      if (data.agent) store.setAgentRunning(data.agent, data.log ?? "")
    })

    es.addEventListener("agent_complete", (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      if (data.agent) store.setAgentDone(data.agent, data.log ?? "", data.output)
    })

    es.addEventListener("hitl_required", (e) => {
      const payload = JSON.parse((e as MessageEvent).data) as HitlPayload
      store.setHitlPayload(payload)
      es.close()
    })

    es.addEventListener("complete", (e) => {
      const data = JSON.parse((e as MessageEvent).data)
      store.setComplete(
        data.brief ?? "",
        (data.sources ?? []) as Source[],
      )
      es.close()
    })

    es.addEventListener("aborted", () => {
      store.reset()
      es.close()
    })

    es.addEventListener("error", (e) => {
      if ("data" in e) {
        try {
          const data = JSON.parse((e as MessageEvent).data)
          store.setError(data.message ?? "Stream error")
        } catch {
          store.setError("Stream connection lost")
        }
      }
      es.close()
    })

    es.addEventListener("done", () => es.close())

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return
      store.setError(
        "Cannot connect to FirmSignal backend. Is it running on port 8000?",
      )
      es.close()
    }

    return () => es.close()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])
}