import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, PackageCheck, Wrench } from "lucide-react";
import { useRef, useState } from "react";
import { api, authedUrl, Concept, Spec } from "../api";
import { useT } from "../i18n";

export default function Workshop() {
  const t = useT();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [category, setCategory] = useState("necklaces");
  const [exportResult, setExportResult] = useState<string>("");

  const specs = useQuery({
    queryKey: ["specs"],
    queryFn: () => api.get<{ specs: Spec[] }>("/api/specs"),
  });
  const concepts = useQuery({
    queryKey: ["concepts"],
    queryFn: () => api.get<{ concepts: Concept[] }>("/api/concepts"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["specs"] });
    queryClient.invalidateQueries({ queryKey: ["concepts"] });
    queryClient.invalidateQueries({ queryKey: ["assets"] });
  };

  const createSpec = useMutation({
    mutationFn: (conceptId: number) =>
      api.post("/api/specs", {
        concept_id: conceptId,
        components: [{ part: "main body" }, { part: "attachment" }],
      }),
    onSuccess: invalidate,
  });
  const setBand = useMutation({
    mutationFn: ({ id, band }: { id: number; band: string }) =>
      api.post(`/api/specs/${id}/band`, { band }),
    onSuccess: invalidate,
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      form.append("category", category);
      const res = await fetch(authedUrl("/api/photographs"), { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: invalidate,
  });
  const runExport = useMutation({
    mutationFn: () =>
      api.post<{ exported: boolean; destination?: string; reason?: string }>("/api/exports", {
        targets: ["flat", "tree", "products_json"],
      }),
    onSuccess: (r) => setExportResult(r.exported ? `→ exports/catalogue/${r.destination}` : r.reason ?? ""),
  });

  const approvedConcepts = (concepts.data?.concepts ?? []).filter((c) => c.status === "approved");

  return (
    <div className="space-y-6">
      <h2 className="font-display text-2xl">{t("workshop")}</h2>

      {approvedConcepts.length > 0 && (
        <section className="card p-4">
          <h3 className="font-display text-sm mb-2 flex items-center gap-2">
            <Wrench size={15} /> Approved concepts awaiting spec
          </h3>
          <div className="flex flex-wrap gap-2">
            {approvedConcepts.map((c) => (
              <button key={c.id} className="btn !text-xs" onClick={() => createSpec.mutate(c.id)}>
                Spec concept #{c.id}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="grid md:grid-cols-2 gap-4">
        {(specs.data?.specs ?? []).map((s) => (
          <div key={s.id} className="card p-4 text-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-medium">Spec #{s.id} · concept #{s.concept_id}</span>
              <span className="chip">{s.state}</span>
            </div>
            <div className="text-xs text-stone-500">
              components: {s.components.map((c) => c.part).join(", ") || "—"}
            </div>
            <div className="flex items-center gap-2 text-xs">
              band:
              {["A", "B", "C", "D"].map((b) => (
                <button key={b}
                        className={`chip ${s.complexity_band === b ? "!border-accent !text-accent" : ""}`}
                        onClick={() => setBand.mutate({ id: s.id, band: b })}>
                  {b}
                </button>
              ))}
              {s.starting_price_aed > 0 && (
                <span className="ms-auto">{t("starting_price")}: <b>{s.starting_price_aed}</b></span>
              )}
            </div>
            {s.open_questions.length > 0 && (
              <div className="text-xs">
                <span className="text-stone-400">{t("open_questions")}:</span>
                <ul className="list-disc ms-4">
                  {s.open_questions.map((q, i) => <li key={i}>{q}</li>)}
                </ul>
              </div>
            )}
            <div className="text-xs text-stone-400">
              materials: {Object.entries(s.materials).filter(([k]) => k !== "verified_source")
                .map(([k, v]) => `${k}=${v}`).slice(0, 4).join(" · ")}
            </div>
          </div>
        ))}
        {!specs.data?.specs.length && <p className="text-stone-400 text-sm">—</p>}
      </section>

      <section className="card p-4">
        <h3 className="font-display text-sm mb-2 flex items-center gap-2">
          <Camera size={15} /> {t("upload_photo")}
        </h3>
        <div className="flex items-center gap-2">
          <select aria-label="photograph category" className="border border-stone-300 rounded px-2 py-1.5 text-sm"
                  value={category} onChange={(e) => setCategory(e.target.value)}>
            {["necklaces", "bracelets", "anklets", "rings", "earrings", "gift_sets",
              "kids", "brooches", "mens_chains", "car_hangers_keychains"].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input ref={fileInput} aria-label="upload workshop photograph" type="file" accept="image/*" className="text-sm"
                 onChange={(e) => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
        </div>
        {upload.error && <p className="text-deny text-xs mt-2">{String(upload.error)}</p>}
      </section>

      <section className="card p-4">
        <h3 className="font-display text-sm mb-1 flex items-center gap-2">
          <PackageCheck size={15} /> {t("export")}
        </h3>
        <p className="text-xs text-stone-400 mb-2">{t("export_note")}</p>
        <button className="btn-primary" disabled={runExport.isPending} onClick={async () => {
          const sel = await api.get<{ assets: unknown[] }>("/api/assets?origin=workshop_photograph");
          const n = sel.assets.length;
          if (n === 0 || window.confirm(t("confirm_export").replace("{n}", String(n)))) runExport.mutate();
        }}>
          {t("export")}: flat + tree + products.json
        </button>
        {exportResult && <p className="text-ok text-xs mt-2">{exportResult}</p>}
        {runExport.error && <p className="text-deny text-xs mt-2">{String(runExport.error)}</p>}
      </section>
    </div>
  );
}
