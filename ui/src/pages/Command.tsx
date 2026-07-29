/**
 * Command Center — executive oversight view.
 *
 * Obsidian-dark, animated, and mobile-first, but every number is real BSOS
 * telemetry: synapse load = kernel tool-call activity from the ledger,
 * coherence = corpus readiness vs the P4 floor, specialist cards = the five
 * kernel agents with owner-set names and uploaded photos, and the
 * intelligence stream is the live policy feed.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, AgentInfo, authedUrl, CorpusHealth, Escalation, FeedEvent } from "../api";
import { DEMO, startDemoFeed } from "../demo";
import { useT } from "../i18n";

const DEFAULT_PERSONAS: Record<string, string> = {
  custodian: "Zaid",
  analyst: "Layla",
  designer: "Amir",
  producer: "Hana",
  publisher: "Noor",
};

function Particles() {
  const particles = useMemo(
    () =>
      Array.from({ length: 22 }, (_, i) => ({
        left: `${(i * 37 + 11) % 100}%`,
        top: `${(i * 53 + 7) % 100}%`,
        size: 2 + ((i * 7) % 4),
        dx: `${((i * 13) % 40) - 20}px`,
        dy: `${((i * 29) % 60) - 30}px`,
        dur: `${9 + ((i * 3) % 8)}s`,
      })),
    [],
  );
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      {particles.map((p, i) => (
        <span
          key={i}
          className="particle"
          style={{
            left: p.left, top: p.top, width: p.size, height: p.size,
            ["--dx" as string]: p.dx, ["--dy" as string]: p.dy,
            ["--dur" as string]: p.dur,
          }}
        />
      ))}
    </div>
  );
}

function MetricBar({ label, sub, value }: { label: string; sub: string; value: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className="glass p-4 fade-slide">
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-sm font-medium tracking-wide">{label}</span>
        <span className="text-xs text-stone-300 tabular-nums">{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full shimmer-bar" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[11px] text-stone-400 mt-1.5">{sub}</p>
    </div>
  );
}

function AgentCard({ agent, hasAvatar, onUpload }: {
  agent: AgentInfo;
  hasAvatar: boolean;
  onUpload: (name: string, file: File) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const display = agent.display_name || DEFAULT_PERSONAS[agent.name] || agent.name;
  return (
    <div className="glass p-4 fade-slide flex flex-col items-center text-center gap-2">
      <div className="relative">
        {hasAvatar ? (
          <img
            src={authedUrl(`/api/agents/${agent.name}/avatar`)}
            alt={display}
            className="w-16 h-16 rounded-full object-cover ring-2 ring-white/20"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-white/10 ring-2 ring-white/20 flex items-center justify-center text-xl font-display">
            {display[0]}
          </div>
        )}
        <span className="status-dot absolute bottom-0.5 end-0.5" />
      </div>
      <div>
        <div className="text-sm font-medium">{display}</div>
        <div className="text-[11px] uppercase tracking-widest text-stone-400">{agent.name}</div>
      </div>
      <p className="text-[11px] text-stone-400 leading-snug line-clamp-2">
        {agent.tagline || agent.role}
      </p>
      <button
        className="text-[11px] px-2 py-0.5 rounded-full border border-white/15 text-stone-300 hover:border-white/40 flex items-center gap-1"
        onClick={() => input.current?.click()}
      >
        <Camera size={11} /> photo
      </button>
      <input
        ref={input} type="file" accept="image/png,image/jpeg,image/webp" hidden
        onChange={(e) => e.target.files?.[0] && onUpload(agent.name, e.target.files[0])}
      />
    </div>
  );
}

export default function Command() {
  const t = useT();
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [avatarVersion, setAvatarVersion] = useState(0);

  const agents = useQuery({
    queryKey: ["agent-profiles"],
    queryFn: () => api.get<{ agents: AgentInfo[] }>("/api/agents/profiles"),
  });
  const health = useQuery({
    queryKey: ["corpus-health"],
    queryFn: () => api.get<CorpusHealth>("/api/corpus/health"),
    refetchInterval: 15000,
  });
  const ledger = useQuery({
    queryKey: ["ledger-activity"],
    queryFn: () => api.get<{ entries: { event_type: string }[] }>("/api/ledger?limit=100"),
    refetchInterval: 10000,
  });
  const escalations = useQuery({
    queryKey: ["escalations"],
    queryFn: () => api.get<{ escalations: Escalation[] }>("/api/escalations"),
    refetchInterval: 10000,
  });

  useEffect(() => {
    if (DEMO) {
      return startDemoFeed((e) => setEvents((prev) => [e, ...prev].slice(0, 40)));
    }
    const source = new EventSource(authedUrl("/api/feed"));
    const onEvent = (e: MessageEvent) => {
      try {
        setEvents((prev) => [JSON.parse(e.data) as FeedEvent, ...prev].slice(0, 40));
      } catch { /* keep stream alive */ }
    };
    ["policy_evaluation", "tool_call", "grant_violation"].forEach((topic) =>
      source.addEventListener(topic, onEvent),
    );
    return () => source.close();
  }, []);

  const upload = useMutation({
    mutationFn: async ({ name, file }: { name: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(authedUrl(`/api/agents/${name}/avatar`), {
        method: "POST", body: form,
      });
      if (!res.ok) throw new Error(await res.text());
    },
    onSuccess: () => {
      setAvatarVersion((v) => v + 1);
      queryClient.invalidateQueries({ queryKey: ["agent-profiles"] });
    },
  });

  const toolCalls = (ledger.data?.entries ?? []).filter((e) => e.event_type === "tool_call").length;
  const synapse = Math.min(1, toolCalls / 100);
  const h = health.data;
  const coherence = h
    ? Math.min(1, (h.references / h.required_references + h.sources / h.required_sources) / 2)
    : 0;
  const openEscalations = escalations.data?.escalations.length ?? 0;

  return (
    <div className="command-theme p-5 sm:p-8 min-h-[85vh]">
      <Particles />
      <div className="relative space-y-6">
        {/* Core */}
        <div className="flex flex-col items-center pt-4 pb-2">
          <div className="relative w-32 h-32">
            <span className="core-ring" />
            <span className="core-ring delay" />
            <div className="core-pulse w-32 h-32 rounded-full bg-gradient-to-br from-[#2b2214] to-[#0d0b07] ring-1 ring-gold/40 flex flex-col items-center justify-center">
              <img src="/brand/logo.png" alt="" className="w-10 h-10 rounded-full mb-1 opacity-90" />
              <span className="font-display text-sm tracking-[0.25em] text-gold-soft">QAIS</span>
              <span className="text-[9px] text-stone-400 tracking-widest">UNIT 01</span>
            </div>
          </div>
          <p className="text-[11px] uppercase tracking-[0.3em] text-stone-400 mt-4">
            {t("core_label")}
          </p>
          {openEscalations > 0 && (
            <p className="text-xs text-amber-300 mt-1 flex items-center gap-1">
              <ShieldAlert size={12} /> {openEscalations} {t("open_decisions")}
            </p>
          )}
        </div>

        {/* Metrics */}
        <div className="grid sm:grid-cols-2 gap-4 max-w-3xl mx-auto">
          <MetricBar label={t("synapse_load")} sub={t("synapse_sub")} value={synapse} />
          <MetricBar label={t("coherence")} sub={t("coherence_sub")} value={coherence} />
        </div>

        {/* Specialist taskforce */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {(agents.data?.agents ?? []).map((a) => (
            <AgentCard
              key={`${a.name}-${avatarVersion}`}
              agent={a}
              hasAvatar={Boolean(a.avatar_path)}
              onUpload={(name, file) => upload.mutate({ name, file })}
            />
          ))}
        </div>

        {/* Intelligence stream */}
        <div className="glass p-4 max-w-3xl mx-auto">
          <h3 className="text-sm font-medium tracking-wide mb-2">{t("intelligence_stream")}</h3>
          <ul className="space-y-1.5 max-h-64 overflow-y-auto">
            {events.length === 0 && (
              <li className="text-xs text-stone-400">{t("no_items")}</li>
            )}
            {events.map((e) => (
              <li key={e.seq} className="fade-slide text-xs flex gap-2 items-start">
                <span className={
                  e.outcome === "deny" || e.outcome === "rejected"
                    ? "text-red-300"
                    : e.outcome === "escalate" ? "text-amber-300" : "text-stone-400"
                }>
                  {e.policy_id ?? e.outcome}
                </span>
                <span className="text-stone-300">
                  {e.agent} · {e.tool}{e.message ? ` — ${e.message}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
