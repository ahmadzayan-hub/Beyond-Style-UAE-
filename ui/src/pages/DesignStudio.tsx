import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck, CheckCircle2, Download, FileWarning, Languages, MonitorPlay, PenTool,
  Ruler, ShieldCheck, Type,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, authedUrl, DesignProjectDetail, DesignProjectSummary } from "../api";
import { DEMO, demoTransliterate } from "../demo";
import { useT } from "../i18n";

/**
 * The customer-visible trust ladder. Each rung is earned in the kernel, never
 * assigned in the UI: spelling by deterministic shaping, manufacturability by
 * geometry validation, approval by a recorded human decision. AI concept
 * imagery (when used elsewhere) never appears on this ladder.
 */
const LADDER = [
  "typography_verified",
  "variants_composed",
  "manufacturing_checked",
  "workshop_approved",
] as const;

function StatusLadder({ status }: { status: string }) {
  const t = useT();
  const reached = LADDER.indexOf(status as (typeof LADDER)[number]);
  if (status === "human_review") {
    return (
      <span className="chip !bg-deny/10 !text-deny !border-deny/30">
        <FileWarning size={11} className="inline me-1" />
        {t("st_human_review")}
      </span>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1">
      {LADDER.map((step, i) => (
        <span
          key={step}
          className={
            i <= reached
              ? "chip !bg-emerald-700/10 !text-emerald-700 !border-emerald-700/30"
              : "chip opacity-40"
          }
        >
          {i <= reached && <CheckCircle2 size={11} className="inline me-1" />}
          {t(`st_${step}`)}
        </span>
      ))}
    </div>
  );
}

export default function DesignStudio() {
  const t = useT();
  const queryClient = useQueryClient();
  const [inscription, setInscription] = useState("");
  const [itemType, setItemType] = useState("cufflink");
  const [selected, setSelected] = useState<number | null>(null);
  const [arabicSuggestions, setArabicSuggestions] = useState<
    { arabic: string; requires_confirmation: boolean; typography_verifiable: boolean }[]
  >([]);

  const hasLatin = /[A-Za-z]/.test(inscription);

  const suggestArabic = async () => {
    const result = DEMO
      ? demoTransliterate(inscription)
      : await api.post<ReturnType<typeof demoTransliterate>>(
          "/api/design/transliterate", { text: inscription });
    const raw = [
      ...result.combined,
      ...(result.words.length === 1 ? result.words[0].suggestions : []),
    ].filter((s) => s.arabic);
    const seen = new Set<string>();
    setArabicSuggestions(raw.filter((s) => !seen.has(s.arabic) && seen.add(s.arabic))
      .map((s) => ({
        arabic: s.arabic,
        requires_confirmation: !!s.requires_confirmation,
        typography_verifiable: !!(s as { typography_verifiable?: boolean }).typography_verifiable,
      })));
  };

  const projects = useQuery({
    queryKey: ["design-projects"],
    queryFn: () => api.get<{ projects: DesignProjectSummary[] }>("/api/design/projects"),
  });
  const detail = useQuery({
    queryKey: ["design-project", selected],
    queryFn: () => api.get<DesignProjectDetail>(`/api/design/projects/${selected}`),
    enabled: selected !== null,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["design-projects"] });
    queryClient.invalidateQueries({ queryKey: ["design-project", selected] });
  };

  const create = useMutation({
    mutationFn: () =>
      api.post<{ project_id: number }>("/api/design/projects", {
        inscription, item_type: itemType,
      }),
    onSuccess: (r) => {
      setInscription("");
      setSelected(r.project_id);
      invalidate();
    },
  });
  const compose = useMutation({
    mutationFn: (id: number) => api.post(`/api/design/projects/${id}/compose`),
    onSuccess: invalidate,
  });
  const validate = useMutation({
    mutationFn: ({ id, variant }: { id: number; variant: string }) =>
      api.post(`/api/design/projects/${id}/validate`, { variant_id: variant }),
    onSuccess: invalidate,
  });
  const approve = useMutation({
    mutationFn: ({ id, variant }: { id: number; variant: string }) =>
      api.post(`/api/design/projects/${id}/approve`, { variant_id: variant, approver: "owner" }),
    onSuccess: invalidate,
  });
  const exportPkg = useMutation({
    mutationFn: (id: number) => api.post(`/api/design/projects/${id}/export`, { brief: {} }),
    onSuccess: invalidate,
  });

  const p = detail.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl flex items-center gap-2">
          <PenTool size={20} /> {t("design_studio")}
        </h2>
        <p className="text-xs text-stone-400 mt-1 max-w-2xl">{t("design_studio_lead")}</p>
      </div>

      <section className="card p-4 space-y-3">
        <h3 className="font-display text-sm flex items-center gap-2">
          <Type size={14} /> {t("new_inscription")}
        </h3>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            dir="auto"
            className="border border-stone-300 rounded px-3 py-2 text-lg w-64"
            placeholder="زهران / Zahran"
            value={inscription}
            onChange={(e) => setInscription(e.target.value)}
          />
          <select
            className="border border-stone-300 rounded px-2 py-2 text-sm"
            value={itemType}
            onChange={(e) => setItemType(e.target.value)}
          >
            {["cufflink", "pendant", "bracelet", "ring", "brooch", "coin", "corporate_gift"].map(
              (v) => (
                <option key={v} value={v}>{t(`item_${v}`)}</option>
              ),
            )}
          </select>
          <button
            className="btn-primary"
            disabled={!inscription.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            <ShieldCheck size={14} className="inline me-1" />
            {t("verify_spelling")}
          </button>
        </div>
        {hasLatin && (
          <div className="space-y-2">
            <button className="btn !text-xs" onClick={suggestArabic}>
              <Languages size={12} className="inline me-1" />
              {t("suggest_arabic")}
            </button>
            {arabicSuggestions.length > 0 && (
              <div className="flex flex-wrap gap-2 items-center">
                {arabicSuggestions.map((s) => (
                  <button key={s.arabic}
                          className={`px-3 py-1.5 rounded border text-lg transition-colors ${
                            s.requires_confirmation
                              ? "border-amber-flag/50 hover:border-amber-flag"
                              : "border-stone-300 hover:border-gold-deep"
                          }`}
                          dir="rtl"
                          onClick={() => { setInscription(s.arabic); setArabicSuggestions([]); }}>
                    {s.arabic}
                    {s.requires_confirmation && (
                      <span className="block text-[9px] text-amber-flag" dir="ltr">
                        {t("confirm_spelling_flag")}
                      </span>
                    )}
                  </button>
                ))}
                <span className="text-[10px] text-stone-400 max-w-[16rem]">{t("suggestion_note")}</span>
              </div>
            )}
          </div>
        )}
        <p className="text-[11px] text-stone-400">{t("spelling_note")}</p>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="card p-3 space-y-1.5 lg:max-h-[70vh] overflow-y-auto">
          <h3 className="font-display text-sm mb-1">{t("projects")}</h3>
          {(projects.data?.projects ?? []).map((proj) => (
            <button
              key={proj.id}
              className={`w-full text-start px-2.5 py-2 rounded border text-sm transition-colors ${
                selected === proj.id
                  ? "border-gold-deep bg-stone-50"
                  : "border-stone-200 hover:border-stone-300"
              }`}
              onClick={() => setSelected(proj.id)}
            >
              <span dir="rtl" className="font-medium text-base">{proj.inscription}</span>
              <span className="block text-[10px] text-stone-400 mt-0.5">
                #{proj.id} · {t(`item_${proj.item_type}`)}
              </span>
              <div className="mt-1"><StatusLadder status={proj.status} /></div>
            </button>
          ))}
          {(projects.data?.projects ?? []).length === 0 && (
            <p className="text-xs text-stone-400">{t("no_items")}</p>
          )}
        </section>

        <section className="lg:col-span-2 space-y-4">
          {!p && <div className="card p-6 text-sm text-stone-400">{t("pick_project")}</div>}
          {p && (
            <>
              <div className="card p-4 space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span dir="rtl" className="font-display text-2xl">{p.inscription}</span>
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusLadder status={p.status} />
                    {p.variants?.length > 0 && (
                      <Link to={`/reveal/${p.id}`} className="btn-primary !text-xs !py-1.5">
                        <MonitorPlay size={13} className="inline me-1" />
                        {t("present_customer")}
                      </Link>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {p.letter_sequence.map((l, i) => (
                    <span key={i} className="chip font-mono" title={l.name}>
                      <span dir="rtl" className="text-sm me-1">{l.char}</span>
                      {l.codepoint}
                    </span>
                  ))}
                </div>
                {p.verification?.issues?.length > 0 && (
                  <ul className="text-xs text-deny list-disc ms-4">
                    {p.verification.issues.map((iss, i) => <li key={i}>{iss}</li>)}
                  </ul>
                )}
                {p.status === "typography_verified" && (
                  <button className="btn-primary" onClick={() => compose.mutate(p.id)}
                          disabled={compose.isPending}>
                    {t("compose_variants")}
                  </button>
                )}
              </div>

              {p.variants?.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {p.variants.map((v) => {
                    const validation = p.validations?.[v.variant_id];
                    const isSelected = p.selected_variant === v.variant_id;
                    return (
                      <div key={v.variant_id}
                           className={`card p-3 space-y-2 ${isSelected ? "border-gold-deep" : ""}`}>
                        <img
                          src={authedUrl(`/api/design/projects/${p.id}/variants/${v.variant_id}.svg`)}
                          alt={v.meta.label_en}
                          className="w-full aspect-square bg-white rounded border border-stone-100"
                        />
                        <div>
                          <p className="text-sm font-medium">{v.meta.label_en}</p>
                          <p dir="rtl" className="text-xs text-stone-500">{v.meta.label_ar}</p>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {v.spelling_verified && (
                            <span className="chip !bg-emerald-700/10 !text-emerald-700 !border-emerald-700/30">
                              <BadgeCheck size={10} className="inline me-0.5" />
                              {t("st_typography_verified")}
                            </span>
                          )}
                          {v.meta.expert_review_recommended && (
                            <span className="chip !bg-amber-flag/10 !text-amber-flag !border-amber-flag/30">
                              {t("expert_review")}
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] text-stone-400 leading-snug">{v.meta.authenticity}</p>
                        {validation && (
                          <ul className="text-[10px] space-y-0.5 font-mono">
                            {validation.checks.map((c) => (
                              <li key={c.check}
                                  className={c.ok ? "text-emerald-700" : "text-deny"}>
                                {c.ok ? "✓" : "✗"} {c.check}
                              </li>
                            ))}
                          </ul>
                        )}
                        {p.status !== "workshop_approved" && (
                          <button className="btn !text-xs w-full"
                                  onClick={() => validate.mutate({ id: p.id, variant: v.variant_id })}
                                  disabled={validate.isPending}>
                            <Ruler size={12} className="inline me-1" />
                            {t("validate_mfg")}
                          </button>
                        )}
                        {isSelected && p.status === "manufacturing_checked" && (
                          <button className="btn-primary !text-xs w-full"
                                  onClick={() => approve.mutate({ id: p.id, variant: v.variant_id })}
                                  disabled={approve.isPending}>
                            {t("approve_workshop")}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {p.status === "workshop_approved" && (
                <div className="card p-4 space-y-2">
                  <h3 className="font-display text-sm">{t("workshop_package")}</h3>
                  {!p.export_manifest?.files ? (
                    <button className="btn-primary" onClick={() => exportPkg.mutate(p.id)}
                            disabled={exportPkg.isPending}>
                      <Download size={14} className="inline me-1" />
                      {t("export_package")}
                    </button>
                  ) : (
                    <>
                      <p className="text-xs text-stone-500">
                        {t("approval_id")}: <code className="font-mono">{p.export_manifest.approval_id}</code>
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.keys(p.export_manifest.files).map((key) => (
                          <a key={key}
                             className="chip hover:border-gold-deep"
                             href={authedUrl(`/api/design/projects/${p.id}/files/${key}`)}
                             target="_blank" rel="noreferrer">
                            <Download size={10} className="inline me-1" />{key}
                          </a>
                        ))}
                      </div>
                      <p className="text-[10px] text-stone-400">{t("package_note")}</p>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
