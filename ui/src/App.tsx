import { useQuery } from "@tanstack/react-query";
import {
  Archive, BadgeCheck, Cpu, Gem, Hammer, Landmark, Languages, LineChart,
  PenTool, ScrollText, ShieldAlert,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, ApiError, authedUrl, Escalation, FeedEvent, getToken, setToken } from "./api";
import { DEMO, startDemoFeed } from "./demo";
import { useLang, useT } from "./i18n";
import Command from "./pages/Command";
import Corpus from "./pages/Corpus";
import Custody from "./pages/Custody";
import DesignStudio from "./pages/DesignStudio";
import Reveal from "./pages/Reveal";
import Studio from "./pages/Studio";
import Trends from "./pages/Trends";
import Workshop from "./pages/Workshop";

const NAV = [
  { to: "/command", key: "command", icon: Cpu },
  { to: "/custody", key: "custody", icon: Archive },
  { to: "/corpus", key: "corpus", icon: Landmark },
  { to: "/trends", key: "trends", icon: LineChart },
  { to: "/studio", key: "studio", icon: Gem },
  { to: "/design", key: "design_studio", icon: PenTool },
  { to: "/workshop", key: "workshop", icon: Hammer },
];

function TokenGate({ children }: { children: React.ReactNode }) {
  const t = useT();
  const [draft, setDraft] = useState(getToken());
  const probe = useQuery({
    queryKey: ["auth-probe", getToken()],
    queryFn: () => api.get<{ ok: boolean }>("/api/policies"),
    retry: false,
  });
  const unauthenticated =
    probe.error instanceof ApiError && (probe.error as ApiError).status === 401;
  if (!unauthenticated) return <>{children}</>;
  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-25">
      <div className="card p-6 w-96 space-y-3">
        <h2 className="font-display text-lg">{t("token_title")}</h2>
        <p className="text-xs text-stone-400">{t("token_hint")}</p>
        <input
          className="border border-stone-300 rounded px-3 py-2 text-sm w-full font-mono"
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (setToken(draft), location.reload())}
        />
        <button className="btn-primary w-full"
                onClick={() => { setToken(draft); location.reload(); }}>
          {t("connect")}
        </button>
      </div>
    </div>
  );
}

function PolicyFeed() {
  const t = useT();
  const [events, setEvents] = useState<FeedEvent[]>([]);
  useEffect(() => {
    if (DEMO) {
      return startDemoFeed((e) => setEvents((prev) => [e, ...prev].slice(0, 60)));
    }
    const source = new EventSource(authedUrl("/api/feed"));
    const onEvent = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as FeedEvent;
        setEvents((prev) => [data, ...prev].slice(0, 60));
      } catch {
        /* keep stream alive */
      }
    };
    source.addEventListener("policy_evaluation", onEvent);
    source.addEventListener("tool_call", onEvent);
    source.addEventListener("grant_violation", onEvent);
    return () => source.close();
  }, []);
  const highlighted = events.filter(
    (e) => e.outcome === "deny" || e.outcome === "escalate" || e.outcome === "rejected",
  );
  return (
    <div className="card p-3 max-h-[40vh] overflow-y-auto">
      <h3 className="font-display text-sm mb-2 flex items-center gap-2">
        <ScrollText size={14} /> {t("policy_feed")}
      </h3>
      <ul className="space-y-1.5 text-xs">
        {(highlighted.length ? highlighted : events.slice(0, 12)).map((e) => (
          <li key={e.seq} className="flex gap-2 items-start">
            <span
              className={
                e.outcome === "deny" || e.outcome === "rejected"
                  ? "chip !bg-deny/10 !text-deny !border-deny/30"
                  : e.outcome === "escalate"
                    ? "chip !bg-amber-flag/10 !text-amber-flag !border-amber-flag/30"
                    : "chip"
              }
            >
              {e.policy_id ?? e.outcome}
            </span>
            <span className="text-stone-500 leading-snug">
              <b>{e.agent}</b> · {e.tool} — {e.message ?? e.outcome}
            </span>
          </li>
        ))}
        {events.length === 0 && <li className="text-stone-400">—</li>}
      </ul>
    </div>
  );
}

function Escalations() {
  const t = useT();
  const { data, refetch } = useQuery({
    queryKey: ["escalations"],
    queryFn: () => api.get<{ escalations: Escalation[] }>("/api/escalations"),
    refetchInterval: 8000,
  });
  const items = data?.escalations ?? [];
  if (!items.length) return null;
  return (
    <div className="card p-3 border-amber-flag/40">
      <h3 className="font-display text-sm mb-2 flex items-center gap-2 text-amber-flag">
        <ShieldAlert size={14} /> {t("escalations")} ({items.length})
      </h3>
      {items.map((e) => (
        <div key={e.id} className="text-xs mb-2 pb-2 border-b border-stone-100 last:border-0">
          <div className="chip mb-1">{e.policy_id}</div>
          <p className="text-stone-500 mb-1">{e.message}</p>
          <div className="flex gap-2">
            <button
              className="btn !py-0.5 !px-2 !text-xs"
              onClick={() =>
                api.post(`/api/escalations/${e.id}/resolve`, { decision: "approved" }).then(() => refetch())
              }
            >
              <BadgeCheck size={12} className="inline me-1" />
              {t("approve")}
            </button>
            <button
              className="btn !py-0.5 !px-2 !text-xs !text-deny"
              onClick={() => {
                if (!window.confirm(t("confirm_reject"))) return;
                api.post(`/api/escalations/${e.id}/resolve`, { decision: "rejected" }).then(() => refetch());
              }}
            >
              {t("reject")}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const t = useT();
  const { lang, setLang } = useLang();
  const location = useLocation();
  // Showroom mode: the Reveal screen is a full-bleed customer view with no
  // operator chrome — what the customer sees on the studio screen or phone.
  if (location.pathname.startsWith("/reveal")) {
    return (
      <TokenGate>
        <Routes>
          <Route path="/reveal/:id" element={<Reveal />} />
          <Route path="/reveal" element={<Navigate to="/reveal/1" replace />} />
        </Routes>
      </TokenGate>
    );
  }
  return (
    <TokenGate>
    {DEMO && (
      <div className="bg-amber-flag text-white text-xs text-center py-1.5 px-3">
        Hosted preview — the Design Studio runs the real deterministic pipeline
        live (type any name). Kernel workflows (approvals, custody, ledger) run
        locally with <code className="font-mono">make dev</code>.
      </div>
    )}
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Mobile-first: compact top bar with horizontal nav on phones. */}
      <div className="lg:hidden border-b border-stone-200 bg-white px-3 pt-2 pb-1.5 sticky top-0 z-20">
        <div className="flex items-center gap-2.5 mb-1.5">
          <img src="/brand/logo.png" alt="Beyond Style" className="w-8 h-8 rounded-full shadow-sm" />
          <h1 className="font-display text-sm tracking-wide flex-1">Beyond Style</h1>
          <button className="btn !py-1 !px-2 !text-xs flex items-center gap-1"
                  onClick={() => setLang(lang === "en" ? "ar" : "en")}
                  aria-label="toggle language">
            <Languages size={12} /> {lang === "en" ? "ع" : "EN"}
          </button>
        </div>
        <nav className="flex gap-1 overflow-x-auto pb-1 -mx-1 px-1">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs whitespace-nowrap transition-colors ${
                  isActive ? "bg-ink text-white" : "bg-stone-100 text-stone-500"
                }`
              }>
              <Icon size={13} /> {t(key)}
            </NavLink>
          ))}
        </nav>
      </div>
      <aside className="hidden lg:flex w-56 shrink-0 border-e border-stone-200 bg-white p-4 flex-col gap-6">
        <div className="flex items-center gap-3">
          <img src="/brand/logo.png" alt="Beyond Style" className="w-12 h-12 rounded-full shadow-sm" />
          <div>
            <h1 className="font-display text-base leading-tight tracking-wide">Beyond Style</h1>
            <p className="text-[10px] text-gold-deep tracking-[0.2em] uppercase mt-0.5">BSOS · Agentic OS</p>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors ${
                  isActive ? "bg-stone-100 text-ink font-medium" : "text-stone-500 hover:text-ink"
                }`
              }
            >
              <Icon size={16} /> {t(key)}
            </NavLink>
          ))}
        </nav>
        <button
          className="btn mt-auto flex items-center gap-2 justify-center"
          onClick={() => setLang(lang === "en" ? "ar" : "en")}
          aria-label="toggle language"
        >
          <Languages size={14} /> {lang === "en" ? "العربية" : "English"}
        </button>
      </aside>
      <main className="flex-1 p-4 sm:p-6 max-w-6xl">
        <Routes>
          <Route path="/" element={<Navigate to="/command" replace />} />
          <Route path="/command" element={<Command />} />
          <Route path="/custody" element={<Custody />} />
          <Route path="/corpus" element={<Corpus />} />
          <Route path="/trends" element={<Trends />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/design" element={<DesignStudio />} />
          <Route path="/workshop" element={<Workshop />} />
        </Routes>
      </main>
      <aside className="w-80 shrink-0 p-4 space-y-4 hidden xl:block">
        <Escalations />
        <PolicyFeed />
      </aside>
    </div>
    </TokenGate>
  );
}
