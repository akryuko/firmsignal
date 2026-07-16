import { create } from "zustand"
import {
  AgentOutputs,
  AgentStatus,
  HitlPayload,
  PricePoint,
  Screen,
  Source,
} from "@/types"

interface AgentState {
  status: AgentStatus
  log: string
}

interface RunStore {
  runId:          string | null
  company:        string
  correctionNote: string | null
  screen:         Screen
  agents:         Record<string, AgentState>
  outputs:        AgentOutputs
  priceHistory:   PricePoint[]
  ticker:         string | null
  hitlPayload:    HitlPayload | null
  finalBrief:     string | null
  finalSources:   Source[]
  errorMsg:       string | null

  startRun:       (runId: string, company: string) => void
  setAgentRunning:(agent: string, log: string) => void
  setAgentDone:   (agent: string, log: string, output?: unknown) => void
  setCorrection:  (resolved: string, note: string) => void
  setHitlPayload: (payload: HitlPayload) => void
  setComplete:    (brief: string, sources: Source[]) => void
  setError:       (msg: string) => void
  reset:          () => void
}

const initialAgents: Record<string, AgentState> = {
  scout:       { status: "pending", log: "" },
  accountant:  { status: "pending", log: "" },
  skeptic:     { status: "pending", log: "" },
  synthesizer: { status: "pending", log: "" },
}

export const useRunStore = create<RunStore>((set) => ({
  runId:          null,
  company:        "",
  correctionNote: null,
  screen:         "search",
  agents:         initialAgents,
  outputs:        {},
  priceHistory:   [],
  ticker:         null,
  hitlPayload:    null,
  finalBrief:     null,
  finalSources:   [],
  errorMsg:       null,

  startRun: (runId, company) => set({
    runId,
    company,
    screen:         "running",
    agents:         { ...initialAgents },
    outputs:        {},
    priceHistory:   [],
    ticker:         null,
    hitlPayload:    null,
    finalBrief:     null,
    finalSources:   [],
    correctionNote: null,
    errorMsg:       null,
  }),

  setAgentRunning: (agent, log) =>
    set((s) => ({
      agents: { ...s.agents, [agent]: { status: "running", log } },
    })),

  setAgentDone: (agent, log, output) =>
    set((s) => {
      const next: Partial<RunStore> = {
        agents: { ...s.agents, [agent]: { status: "done", log } },
      }
      if (output) {
        next.outputs = { ...s.outputs, [agent]: output }
        if (agent === "accountant") {
          const acc = output as { price_history?: PricePoint[]; ticker?: string }
          next.priceHistory = acc.price_history ?? []
          next.ticker       = acc.ticker ?? null
        }
      }
      return next
    }),

  setCorrection: (resolved, note) =>
    set({ company: resolved, correctionNote: note }),

  setHitlPayload: (payload) =>
    set({ hitlPayload: payload, screen: "hitl" }),

  setComplete: (brief, sources) =>
    set({ finalBrief: brief, finalSources: sources, screen: "report" }),

  setError: (msg) =>
    set({ errorMsg: msg, screen: "error" }),

  reset: () =>
    set({
      runId:          null,
      company:        "",
      correctionNote: null,
      screen:         "search",
      agents:         { ...initialAgents },
      outputs:        {},
      priceHistory:   [],
      ticker:         null,
      hitlPayload:    null,
      finalBrief:     null,
      finalSources:   [],
      errorMsg:       null,
    }),
}))