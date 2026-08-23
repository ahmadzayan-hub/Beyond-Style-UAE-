import { useQuery } from "@tanstack/react-query";
import { Compass, Grid3X3, BarChart3 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, WhitespaceEntry } from "../api";
import { useT } from "../i18n";

function BlockedNote({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.decisions.length) {
    return (
      <div className="card p-4 border-amber-flag/40 text-sm">
        <span className="chip !text-amber-flag !border-amber-flag/40 mb-2">
          {error.decisions[0].policy_id}
        </span>
        <p className="text-stone-500">{error.decisions[0].message}</p>
      </div>
    );
  }
  return null;
}

export default function Trends() {
  const t = useT();
  const navigate = useNavigate();
  const whitespace = useQuery({
    queryKey: ["whitespace"],
    queryFn: () => api.get<{ whitespace: WhitespaceEntry[] }>("/api/trends/whitespace"),
    retry: false,
  });
  const frequency = useQuery({
    queryKey: ["frequency"],
    queryFn: () => api.get<{ ranking: Record<string, [string, number][]> }>("/api/trends/frequency"),
    retry: false,
  });
  const cooc = useQuery({
    queryKey: ["cooccurrence"],
    queryFn: () => api.get<{ pairs: { a: string; b: string; count: number }[] }>("/api/trends/cooccurrence"),
    retry: false,
  });

  const maxCount = Math.max(1, ...(cooc.data?.pairs ?? []).map((p) => p.count));

  return (
    <div className="space-y-6">
      <h2 className="font-display text-2xl">{t("trends")}</h2>

      {/* Whitespace leads the screen, deliberately. */}
      <section className="card p-4">
        <h3 className="font-display text-sm mb-1 flex items-center gap-2">
          <Compass size={15} /> {t("whitespace")}
        </h3>
        <p className="text-xs text-stone-400 mb-3">{t("whitespace_lead")}</p>
        {whitespace.error && <BlockedNote error={whitespace.error} />}
        <div className="space-y-2">
          {(whitespace.data?.whitespace ?? []).slice(0, 10).map((w, i) => (
            <div key={i} className="flex items-center justify-between gap-3 border-b border-stone-100 pb-2 last:border-0">
              <div className="text-sm">
                <span className="chip me-1">{w.a}</span>
                <span className="text-stone-400">×</span>
                <span className="chip ms-1">{w.b}</span>
                <div className="text-xs text-stone-400 mt-1">
                  seen together {w.combo_count}× · components {w.a_count}× / {w.b_count}× · score {w.opportunity_score}
                </div>
              </div>
              <button
                className="btn !text-xs shrink-0"
                onClick={() =>
                  navigate(`/studio?seed=${encodeURIComponent(w.a)}&seed=${encodeURIComponent(w.b)}`)
                }
              >
                {t("draft_brief")}
              </button>
            </div>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="card p-4">
          <h3 className="font-display text-sm mb-3 flex items-center gap-2">
            <BarChart3 size={15} /> {t("frequency")}
          </h3>
          {frequency.error && <BlockedNote error={frequency.error} />}
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {Object.entries(frequency.data?.ranking ?? {}).map(([path, entries]) =>
              entries.length ? (
                <div key={path}>
                  <div className="text-xs text-stone-400 mb-1">{path}</div>
                  {entries.slice(0, 4).map(([value, count]) => (
                    <div key={value} className="flex items-center gap-2 text-xs mb-0.5">
                      <span className="w-32 truncate">{value}</span>
                      <div className="flex-1 h-1.5 bg-stone-100 rounded">
                        <div className="h-full bg-stone-400 rounded"
                             style={{ width: `${Math.min(100, count * 8)}%` }} />
                      </div>
                      <span className="text-stone-400 w-6 text-end">{count}</span>
                    </div>
                  ))}
                </div>
              ) : null,
            )}
          </div>
        </section>

        <section className="card p-4">
          <h3 className="font-display text-sm mb-3 flex items-center gap-2">
            <Grid3X3 size={15} /> {t("cooccurrence")}
          </h3>
          {cooc.error && <BlockedNote error={cooc.error} />}
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {(cooc.data?.pairs ?? []).slice(0, 30).map((p, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span
                  className="inline-block w-3 h-3 rounded-sm"
                  style={{ backgroundColor: `rgba(125,103,72,${0.15 + 0.85 * (p.count / maxCount)})` }}
                />
                <span className="truncate">{p.a} × {p.b}</span>
                <span className="text-stone-400 ms-auto">{p.count}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
