import { useQuery } from "@tanstack/react-query";
import {
  Archive, BadgeCheck, Gem, Hammer, Landmark, Languages, LineChart,
  ScrollText, ShieldAlert,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api, Escalation, FeedEvent } from "./api";
import { useLang, useT } from "./i18n";
import Corpus from "./pages/Corpus";
import Custody from "./pages/Custody";
import Studio from "./pages/Studio";
import Trends from "./pages/Trends";
import Workshop from "./pages/Workshop";

const NAV = [
  { to: "/custody", key: "custody", icon: Archive },
  { to: "/corpus", key: "corpus", icon: Landmark },
  { to: "/trends", key: "trends", icon: LineChart },
  { to: "/studio", key: "studio", icon: Gem },
  { to: "/workshop", key: "workshop", icon: Hammer },
];

function PolicyFeed() {
  const t = useT();
  const [events, setEvents] = useState<FeedEvent[]>([]);
  useEffect(() => {
    const source = new EventSource("/api/feed");
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
              onClick={() =>
                api.post(`/api/escalations/${e.id}/resolve`, { decision: "rejected" }).then(() => refetch())
              }
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
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-e border-stone-200 bg-white p-4 flex flex-col gap-6">
        <div>
          <h1 className="font-display text-xl tracking-wide">Beyond Style</h1>
          <p className="text-xs text-stone-400 mt-0.5">BSOS · agentic OS</p>
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
      <main className="flex-1 p-6 max-w-6xl">
        <Routes>
          <Route path="/" element={<Navigate to="/custody" replace />} />
          <Route path="/custody" element={<Custody />} />
          <Route path="/corpus" element={<Corpus />} />
          <Route path="/trends" element={<Trends />} />
          <Route path="/studio" element={<Studio />} />
          <Route path="/workshop" element={<Workshop />} />
        </Routes>
      </main>
      <aside className="w-80 shrink-0 p-4 space-y-4 hidden xl:block">
        <Escalations />
        <PolicyFeed />
      </aside>
    </div>
  );
}
