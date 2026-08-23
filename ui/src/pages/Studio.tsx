import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Info, Wand2, XCircle } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, authedUrl, Brief, Concept } from "../api";
import { useT } from "../i18n";

const MIN_SOURCES = 3;

export default function Studio() {
  const t = useT();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const seeds = params.getAll("seed");
  const [title, setTitle] = useState("");
  const [seedText, setSeedText] = useState(seeds.join("\n"));
  const [model, setModel] = useState("local-dev");

  const briefs = useQuery({
    queryKey: ["briefs"],
    queryFn: () => api.get<{ briefs: Brief[] }>("/api/briefs"),
  });
  const concepts = useQuery({
    queryKey: ["concepts"],
    queryFn: () => api.get<{ concepts: Concept[] }>("/api/concepts"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["briefs"] });
    queryClient.invalidateQueries({ queryKey: ["concepts"] });
  };

  const compose = useMutation({
    mutationFn: () =>
      api.post("/api/briefs", {
        title: title || "untitled brief",
        seed_values: seedText.split("\n").map((s) => s.trim()).filter(Boolean),
      }),
    onSuccess: invalidate,
  });
  const promote = useMutation({
    mutationFn: (id: number) => api.post(`/api/briefs/${id}/promote`),
    onSuccess: invalidate,
  });
  const generate = useMutation({
    mutationFn: (id: number) => api.post("/api/concepts/generate", { brief_id: id, model }),
    onSuccess: invalidate,
  });
  const promoteConcept = useMutation({
    mutationFn: (id: number) => api.post(`/api/concepts/${id}/promote`, {}),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-6">
      <h2 className="font-display text-2xl">{t("studio")}</h2>

      <section className="card p-4">
        <h3 className="font-display text-sm mb-3 flex items-center gap-2">
          <Wand2 size={15} /> {t("briefs")}
        </h3>
        <div className="grid md:grid-cols-2 gap-3 mb-3">
          <input
            className="border border-stone-300 rounded px-3 py-2 text-sm"
            placeholder="brief title" aria-label="brief title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="border border-stone-300 rounded px-3 py-2 text-sm"
            placeholder="imagegen model id" aria-label="image generation model id"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
        </div>
        <textarea
          className="border border-stone-300 rounded px-3 py-2 text-sm w-full h-20 font-mono"
          aria-label="brief seed values" placeholder={"one seed per line, e.g.\nmotif.primary=falcon\nform.silhouette=bar"}
          value={seedText}
          onChange={(e) => setSeedText(e.target.value)}
        />
        <button className="btn-primary mt-2" disabled={compose.isPending} onClick={() => compose.mutate()}>
          Compose brief
        </button>
        {compose.error && <p className="text-deny text-xs mt-2">{String(compose.error)}</p>}
        {promote.error && <p className="text-deny text-xs mt-2">{String(promote.error)}</p>}
      </section>

      <section className="space-y-3">
        {(briefs.data?.briefs ?? []).map((b) => (
          <div key={b.id} className="card p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium text-sm">
                #{b.id} · {b.title} <span className="chip ms-2">{b.status}</span>
              </div>
              <div className="flex gap-2">
                {b.status !== "approved" && (
                  <button className="btn !text-xs" onClick={() => promote.mutate(b.id)}>
                    {t("promote")}
                  </button>
                )}
                {b.status === "approved" && (
                  <button className="btn-primary !text-xs" disabled={generate.isPending}
                          onClick={() => generate.mutate(b.id)}>
                    {t("generate")}
                  </button>
                )}
              </div>
            </div>
            {/* live provenance counts, colour-coded against the 3-source minimum */}
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(b.attributes).map(([path, meta]) => {
                const n = new Set(meta.source_ids).size;
                const ok = n >= MIN_SOURCES;
                return (
                  <span key={path}
                        className={`chip ${ok ? "!border-ok/40 !text-ok" : "!border-deny/40 !text-deny"}`}>
                    {path}={meta.value} · {n}/{MIN_SOURCES}
                  </span>
                );
              })}
              {Object.keys(b.dropped_attributes ?? {}).map((path) => (
                <span key={path} className="chip line-through opacity-60">{path}</span>
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {(concepts.data?.concepts ?? []).map((c) => {
          const gate = c.gate_result ?? {};
          const passed = gate.passed;
          return (
            <figure key={c.id} className="card overflow-hidden relative">
              <img src={authedUrl(`/api/concepts/${c.id}/image`)} alt={`concept ${c.id}`}
                   className="aspect-square object-cover w-full" loading="lazy" />
              {/* visible CONCEPT_ONLY overlay on every preview */}
              <div className="absolute top-2 start-2 chip !bg-white/85 !text-stone-500 tracking-widest">
                {t("concept_only")}
              </div>
              <figcaption className="p-2 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span>#{c.id} · {c.model_id}</span>
                  {passed === true && (
                    <span className="text-ok flex items-center gap-1">
                      <CheckCircle2 size={12} /> {t("gate_passed")}
                      {gate.advisory && (
                        <span className="chip !border-amber-flag/50 !text-amber-flag"
                              title={t("advisory_gate_note")}>
                          {t("advisory")}
                        </span>
                      )}
                    </span>
                  )}
                  {passed === false && (
                    <span className="text-amber-flag flex items-center gap-1">
                      <XCircle size={12} /> {t("gate_rejected")} {gate.max_similarity?.toFixed(3)}
                    </span>
                  )}
                </div>
                {gate.nearest && gate.nearest.length > 0 && (
                  <div className="text-stone-400 flex items-center gap-1">
                    <Info size={11} /> {t("nearest_refs")}:{" "}
                    {gate.nearest.map((n) => `${n.key.replace("corpus:", "").slice(0, 6)}·${n.similarity.toFixed(2)}`).join(", ")}
                  </div>
                )}
                {c.status === "gate_passed" && (
                  <button className="btn !text-xs w-full"
                          disabled={promoteConcept.isPending}
                          onClick={() => promoteConcept.mutate(c.id)}>
                    {t("promote")}
                  </button>
                )}
                <span className="chip">{c.status}</span>
              </figcaption>
            </figure>
          );
        })}
      </section>
      {promoteConcept.error && <p className="text-deny text-xs">{String(promoteConcept.error)}</p>}
    </div>
  );
}
