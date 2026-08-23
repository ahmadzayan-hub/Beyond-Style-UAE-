import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gauge, Sparkles } from "lucide-react";
import { api, Asset, CorpusHealth } from "../api";
import { useT } from "../i18n";

interface CorpusRef {
  id: number;
  source_id: string;
  source_handle: string;
  attributes: Record<string, Record<string, unknown>>;
}

function chips(ref: CorpusRef): string[] {
  const out: string[] = [];
  for (const section of Object.values(ref.attributes)) {
    for (const value of Object.values(section)) {
      if (typeof value === "string" && value) out.push(value);
    }
  }
  return out.slice(0, 8);
}

export default function Corpus() {
  const t = useT();
  const queryClient = useQueryClient();
  const health = useQuery({
    queryKey: ["corpus-health"],
    queryFn: () => api.get<CorpusHealth>("/api/corpus/health"),
  });
  const refs = useQuery({
    queryKey: ["corpus-refs"],
    queryFn: () => api.get<{ rows: CorpusRef[] }>("/api/corpus/refs"),
  });
  const assets = useQuery({
    queryKey: ["assets", ""],
    queryFn: () => api.get<{ assets: Asset[] }>("/api/assets"),
  });
  const extract = useMutation({
    mutationFn: (assetId: string) => api.post(`/api/assets/${assetId}/extract`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["corpus-health"] });
      queryClient.invalidateQueries({ queryKey: ["corpus-refs"] });
    },
  });

  const h = health.data;
  const inCorpus = new Set((refs.data?.rows ?? []).map((r) => r.source_id));
  const candidates = (assets.data?.assets ?? []).filter(
    (a) => !inCorpus.has(a.id) && a.review_state === "clear" && a.origin !== "ai_generated",
  );

  return (
    <div className="space-y-6">
      <h2 className="font-display text-2xl">{t("corpus")}</h2>

      <section className="card p-4">
        <h3 className="font-display text-sm mb-3 flex items-center gap-2">
          <Gauge size={15} /> {t("corpus_health")}
        </h3>
        {h && (
          <div className="space-y-3">
            {[
              { label: t("references"), value: h.references, req: h.required_references },
              { label: t("sources"), value: h.sources, req: h.required_sources },
            ].map(({ label, value, req }) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span>{value} / {req} {label}</span>
                </div>
                <div className="h-2 bg-stone-100 rounded overflow-hidden">
                  <div
                    className={`h-full ${value >= req ? "bg-ok" : "bg-amber-flag"}`}
                    style={{ width: `${Math.min(100, (value / req) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
            {!h.floor_met && <p className="text-amber-flag text-sm">{t("floor_blocked")}</p>}
          </div>
        )}
      </section>

      {candidates.length > 0 && (
        <section className="card p-4">
          <h3 className="font-display text-sm mb-2 flex items-center gap-2">
            <Sparkles size={15} /> Abstract into corpus ({candidates.length} candidates)
          </h3>
          <div className="flex flex-wrap gap-2">
            {candidates.slice(0, 12).map((a) => (
              <button key={a.id} className="btn !text-xs" disabled={extract.isPending}
                      onClick={() => extract.mutate(a.id)}>
                {a.filename}
              </button>
            ))}
          </div>
          {extract.error && <p className="text-deny text-xs mt-2">{String(extract.error)}</p>}
        </section>
      )}

      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {(refs.data?.rows ?? []).map((r) => (
          <div key={r.id} className="card p-3">
            <div className="text-xs text-stone-400 mb-2">{r.source_handle} · {r.source_id.slice(0, 8)}</div>
            <div className="flex flex-wrap gap-1">
              {chips(r).map((c, i) => (
                <span key={i} className="chip">{c}</span>
              ))}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
