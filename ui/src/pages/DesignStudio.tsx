import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck, CheckCircle2, Download, FileWarning, Languages, MonitorPlay, PenTool,
  Ruler, ShieldCheck, Type,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, authedUrl, DesignProjectDetail, DesignProjectSummary } from "../api";
import { JewelPreview, METAL_STOPS } from "../components/JewelPreview";
import { DEMO, demoTransliterate } from "../demo";
import { useLang, useT } from "../i18n";

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

interface LivePreview {
  input: string;
  normalized: string;
  status: string;
  arabic_part?: string;
  latin_part?: string;
  letter_sequence: { char: string; codepoint: string; name: string }[];
  verification: { passed: boolean; issues: string[]; issues_ar?: string[] };
  variants: {
    variant_id: string;
    svg: string;
    spelling_verified: boolean;
    validation_passed: boolean;
    failed_checks: string[];
    price_from_aed: number | null;
    meta: { label_en: string; label_ar: string; authenticity: string };
  }[];
}

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
  const { lang } = useLang();
  const queryClient = useQueryClient();
  const [inscription, setInscription] = useState("");
  const [itemType, setItemType] = useState(DEMO ? "" : "cufflink");
  // What the imagine parser understood from the customer's sentence, plus
  // the no-lettering prompt for the open-source concept-photo model.
  const [intent, setIntent] = useState<{
    inscription: string; item: string; material: string; finish: string;
    style_variant: string; item_detected: boolean; material_detected: boolean;
    photo_prompt: string;
  } | null>(null);
  const [conceptState, setConceptState] = useState<"loading" | "ready" | "failed">("loading");
  const [selected, setSelected] = useState<number | null>(null);
  const [arabicSuggestions, setArabicSuggestions] = useState<
    { arabic: string; requires_confirmation: boolean; typography_verifiable: boolean }[]
  >([]);
  const [live, setLive] = useState<LivePreview | null>(null);
  const [liveBusy, setLiveBusy] = useState(false);
  const [liveError, setLiveError] = useState("");
  const [liveVariantId, setLiveVariantId] = useState("manufacturing_optimized");
  const [liveMaterial, setLiveMaterial] = useState("silver_925");
  const [liveFinish, setLiveFinish] = useState("black_enamel");

  const hasLatin = /[A-Za-z]/.test(inscription);

  // Landing showcase: a finished sample piece cycling through materials,
  // so the first screen opens on a final design instead of an empty form.
  const [showcaseSvg, setShowcaseSvg] = useState("");
  const [showcaseMat, setShowcaseMat] = useState(0);
  const MATS = Object.keys(METAL_STOPS);

  // Warm the serverless pipeline so the first generation feels instant.
  useEffect(() => {
    if (DEMO) fetch("/api/studio/health").catch(() => {});
    fetch("/demo/design_manufacturing_optimized.svg")
      .then((r) => (r.ok ? r.text() : ""))
      .then(setShowcaseSvg)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (live) return;
    const timer = setInterval(() => setShowcaseMat((i) => i + 1), 2600);
    return () => clearInterval(timer);
  }, [live]);

  // Hosted preview: the static demo cannot reach the kernel API, but the
  // REAL deterministic pipeline runs serverless at /api/studio/* — any name
  // typed here produces genuine verified variants, validation and prices.
  const runLive = async (textOverride?: string) => {
    const text = textOverride ?? inscription;
    if (textOverride) setInscription(textOverride);
    setLiveBusy(true);
    setLiveError("");
    try {
      const res = await fetch(
        `/api/studio/preview?text=${encodeURIComponent(text)}&item=${itemType || "pendant"}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setLive(data);
      setTimeout(() =>
        document.getElementById("live-results")?.scrollIntoView({ behavior: "smooth" }), 80);
    } catch {
      setLive(null);
      setLiveError(t("live_error"));
    } finally {
      setLiveBusy(false);
    }
  };

  // Imagine mode: a whole sentence ("خاتم ذهب باسم نورة") is parsed into
  // item + material + style + inscription server-side, then the inscription
  // runs through the SAME fail-closed verification as a typed name.
  const runImagine = async () => {
    setLiveBusy(true);
    setLiveError("");
    try {
      const res = await fetch(
        `/api/studio/imagine?text=${encodeURIComponent(inscription)}` +
        (itemType ? `&item=${itemType}` : ""));
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const it = data.intent;
      setIntent(it);
      setItemType(it.item);
      if (it.material_detected) setLiveMaterial(it.material);
      setLiveFinish(it.finish);
      setLiveVariantId(it.style_variant);
      setConceptState("loading");
      if (data.preview) {
        setLive(data.preview);
        setTimeout(() =>
          document.getElementById("live-results")?.scrollIntoView({ behavior: "smooth" }), 80);
      } else {
        setLive(null);
        const issues = data.verification ?? {};
        setLiveError(
          (lang === "ar" ? issues.issues_ar?.[0] : issues.issues?.[0]) ?? t("live_error"));
      }
    } catch {
      setLive(null);
      setLiveError(t("live_error"));
    } finally {
      setLiveBusy(false);
    }
  };

  // Stable seed so the same wish redraws the same concept photo.
  const conceptSeed = intent
    ? Array.from(intent.photo_prompt).reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 999983, 7)
    : 0;
  const conceptUrl = intent
    ? `https://image.pollinations.ai/prompt/${encodeURIComponent(intent.photo_prompt)}` +
      `?width=768&height=768&model=flux&nologo=true&seed=${conceptSeed}`
    : "";


  const suggestArabic = async () => {
    let result: ReturnType<typeof demoTransliterate>;
    if (DEMO) {
      try {
        const res = await fetch(`/api/studio/transliterate?text=${encodeURIComponent(inscription)}`);
        result = res.ok ? await res.json() : demoTransliterate(inscription);
      } catch {
        result = demoTransliterate(inscription);
      }
    } else {
      result = await api.post<ReturnType<typeof demoTransliterate>>(
        "/api/design/transliterate", { text: inscription });
    }
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
        inscription, item_type: itemType || "cufflink",
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

  const submit = () => {
    if (!inscription.trim() || create.isPending || liveBusy) return;
    if (DEMO) runImagine();
    else create.mutate();
  };

  const p = detail.data;

  // Product-look previews for the stored project's variants.
  const [projSvgs, setProjSvgs] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!p?.variants?.length) return;
    p.variants.forEach((v) => {
      const inline = (v as { svg?: string }).svg;
      if (inline) {
        setProjSvgs((prev) => (prev[v.variant_id] ? prev : { ...prev, [v.variant_id]: inline }));
        return;
      }
      fetch(authedUrl(`/api/design/projects/${p.id}/variants/${v.variant_id}.svg`))
        .then((r) => (r.ok ? r.text() : ""))
        .then((txt) => txt && setProjSvgs((prev) => ({ ...prev, [v.variant_id]: txt })))
        .catch(() => {});
    });
  }, [p]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl flex items-center gap-2">
          <PenTool size={20} /> {t("design_studio")}
        </h2>
        <p className="text-xs text-stone-400 mt-1 max-w-2xl">{t("design_studio_lead")}</p>
      </div>

      {!live && (
        <section className="rounded-xl bg-ink p-5 sm:p-6 flex flex-col sm:flex-row items-center gap-5 min-h-[16rem] sm:min-h-[13rem]">
          <div className="w-40 sm:w-48 shrink-0 [&_svg]:w-full [&_svg]:h-auto">
            {showcaseSvg ? (
              <JewelPreview svgText={showcaseSvg}
                            material={MATS[showcaseMat % MATS.length]}
                            finish="black_enamel" size="100%" />
            ) : (
              <div className="w-full aspect-square rounded-full bg-white/10" aria-hidden />
            )}
          </div>
          <div className="text-center sm:text-start">
            <p className="font-display text-gold text-lg leading-snug">{t("showcase_title")}</p>
            <p className="text-stone-100/70 text-xs mt-2 max-w-sm">{t("showcase_sub")}</p>
          </div>
        </section>
      )}

      <section className="card p-4 sm:p-5 space-y-3 border-gold/30">
        <h3 className="font-display text-base flex items-center gap-2">
          <Type size={15} className="text-gold-deep" /> {t("imagine_title")}
        </h3>
        <input
          dir="auto"
          aria-label={t("imagine_title")}
          className="border border-stone-300 focus:border-gold-deep outline-none rounded-lg px-4 py-3 text-lg w-full"
          placeholder={t("imagine_placeholder")}
          value={inscription}
          onChange={(e) => setInscription(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <div className="flex flex-wrap gap-2 items-center">
          <select
            aria-label={t("item_type_label")}
            className="border border-stone-300 rounded px-2 py-2 text-sm"
            value={itemType}
            onChange={(e) => setItemType(e.target.value)}
          >
            {DEMO && <option value="">{t("item_auto")}</option>}
            {["cufflink", "pendant", "bracelet", "ring", "brooch", "coin", "corporate_gift"].map(
              (v) => (
                <option key={v} value={v}>{t(`item_${v}`)}</option>
              ),
            )}
          </select>
          <button
            className="btn-primary"
            disabled={!inscription.trim() || create.isPending || liveBusy}
            onClick={submit}
          >
            <ShieldCheck size={14} className="inline me-1" />
            {liveBusy ? t("generating") : t("imagine_cta")}
          </button>
          {liveError && <span className="text-xs text-deny">{liveError}</span>}
        </div>
        <p className="text-[11px] text-stone-400">{t("imagine_hint")}</p>
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

      {live && (
        <section id="live-results" className="card p-4 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span dir="rtl" className="font-display text-2xl">{live.normalized || live.input}</span>
            <div className="flex items-center gap-2 flex-wrap">
              <StatusLadder status={live.status === "mixed_script" ? "human_review" : live.status} />
              {live.variants.length > 0 && (
                <Link to={`/reveal/live?text=${encodeURIComponent(live.normalized)}&item=${itemType}`}
                      className="btn-primary !text-xs !py-1.5">
                  <MonitorPlay size={13} className="inline me-1" />
                  {t("present_customer")}
                </Link>
              )}
            </div>
          </div>
          {intent && live.variants.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] uppercase tracking-widest text-stone-400">
                {t("understood_as")}
              </span>
              <span className="chip">{t(`item_${intent.item}`)}</span>
              <span className="chip">{t(`fin_${intent.finish}`)}</span>
              <span dir="rtl" className="chip font-medium">{intent.inscription}</span>
            </div>
          )}
          {live.status === "mixed_script" && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-stone-500">{t("mixed_pick")}</span>
              {[live.arabic_part, live.latin_part].filter(Boolean).map((part) => (
                <button key={part} dir="auto"
                        className="px-3 py-1.5 rounded border border-stone-300 hover:border-gold-deep text-base"
                        onClick={() => runLive(part!)}>
                  {part}
                </button>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-1.5">
            {live.letter_sequence.map((l, i) => (
              <span key={i} className="chip font-mono" title={l.name}>
                <span dir="rtl" className="text-sm me-1">{l.char}</span>{l.codepoint}
              </span>
            ))}
          </div>
          {live.verification.issues?.length > 0 && (
            <ul className="text-xs text-deny list-disc ms-4">
              {(lang === "ar" && live.verification.issues_ar?.length
                ? live.verification.issues_ar
                : live.verification.issues
              ).map((iss, i) => <li key={i}>{iss}</li>)}
            </ul>
          )}
          {live.variants.length > 0 && (() => {
            const hero = live.variants.find((v) => v.variant_id === liveVariantId)
              ?? live.variants[live.variants.length - 1];
            return (
              <div className="rounded-xl bg-ink p-4 sm:p-6 flex flex-col items-center gap-3">
                <p className="text-[10px] uppercase tracking-[0.3em] text-gold">
                  {t("final_design")}
                </p>
                <div className="w-full max-w-[340px] [&_svg]:w-full [&_svg]:h-auto">
                  <JewelPreview svgText={hero.svg} material={liveMaterial}
                                finish={liveFinish} size="100%" />
                </div>
                <p className="text-stone-100 text-sm">
                  {hero.meta[lang === "ar" ? "label_ar" : "label_en"]}
                  {hero.price_from_aed != null && (
                    <span className="text-gold ms-2">
                      {t("starting_price_label")}: {hero.price_from_aed} AED
                    </span>
                  )}
                </p>
                <div className="flex gap-2 flex-wrap justify-center">
                  {Object.keys(METAL_STOPS).map((m) => (
                    <button key={m} onClick={() => setLiveMaterial(m)}
                            aria-label={m.replace(/_/g, " ")}
                            aria-pressed={liveMaterial === m}
                            className={`w-8 h-8 rounded-full border-2 transition-all ${
                              liveMaterial === m ? "border-gold scale-110" : "border-stone-500/40"
                            }`}
                            style={{ background: `linear-gradient(135deg, ${METAL_STOPS[m][0]}, ${METAL_STOPS[m][2]})` }} />
                  ))}
                </div>
                <div className="flex gap-1.5 flex-wrap justify-center">
                  {(["black_enamel", "white_enamel", "mirror_polish", "brushed"] as const).map((f) => (
                    <button key={f} onClick={() => setLiveFinish(f)}
                            className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                              liveFinish === f
                                ? "border-gold bg-gold/10 text-gold"
                                : "border-stone-500/40 text-stone-400"
                            }`}>
                      {t(`fin_${f}`)}
                    </button>
                  ))}
                </div>
              </div>
            );
          })()}
          {intent && live.variants.length > 0 && conceptState !== "failed" && (() => {
            const hero = live.variants.find((v) => v.variant_id === liveVariantId)
              ?? live.variants[live.variants.length - 1];
            const darkMetal = liveMaterial === "oxidized_silver";
            return (
              <div className="rounded-xl overflow-hidden bg-ink">
                <div className="relative w-full max-w-[480px] mx-auto aspect-square">
                  {/* Open-source model (FLUX family via pollinations.ai, free) paints
                      the scene with a BLANK face; the verified inscription is layered
                      by us — image models cannot spell Arabic. */}
                  <img
                    src={conceptUrl}
                    alt={t("concept_title")}
                    className={`w-full h-full object-cover transition-opacity duration-700 ${
                      conceptState === "ready" ? "opacity-100" : "opacity-0"
                    }`}
                    onLoad={() => setConceptState("ready")}
                    onError={() => setConceptState("failed")}
                  />
                  {conceptState === "loading" && (
                    <div className="absolute inset-0 flex items-center justify-center" role="status">
                      <div className="w-24 h-24 rounded-full bg-white/5 animate-pulse" />
                    </div>
                  )}
                  {conceptState === "ready" && (
                    <div
                      aria-hidden
                      className="absolute inset-0 flex items-center justify-center pointer-events-none
                                 [&_svg]:w-[38%] [&_svg]:h-auto [&_circle]:hidden"
                      style={{
                        color: darkMetal ? "#e8c987" : "#241c10",
                        mixBlendMode: darkMetal ? "screen" : "multiply",
                        opacity: 0.9,
                        filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.35))",
                      }}
                      dangerouslySetInnerHTML={{
                        __html: hero.svg.replace(/fill="#111111"/g, 'fill="currentColor"'),
                      }}
                    />
                  )}
                  <span className="absolute top-2 start-2 chip !bg-ink/70 !text-gold !border-gold/40 backdrop-blur-sm">
                    {t("concept_chip")}
                  </span>
                </div>
                <p className="text-[10px] text-stone-100/60 px-4 py-2.5">{t("concept_note")}</p>
              </div>
            );
          })()}
          {live.variants.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {live.variants.map((v) => (
                <div key={v.variant_id}
                     className={`card p-3 space-y-2 cursor-pointer transition-colors ${
                       liveVariantId === v.variant_id ? "border-gold-deep" : "hover:border-stone-300"
                     }`}
                     onClick={() => setLiveVariantId(v.variant_id)}>
                  <div className="w-full [&_svg]:w-full [&_svg]:h-auto">
                    <JewelPreview svgText={v.svg} material={liveMaterial}
                                  finish={liveFinish} size="100%" />
                  </div>
                  <p className="text-sm font-medium">{v.meta.label_en}</p>
                  <p dir="rtl" className="text-xs text-stone-500">{v.meta.label_ar}</p>
                  <div className="flex flex-wrap gap-1">
                    <span className="chip !bg-emerald-700/10 !text-emerald-700 !border-emerald-700/30">
                      <BadgeCheck size={10} className="inline me-0.5" />
                      {t("st_typography_verified")}
                    </span>
                    <span className={v.validation_passed
                      ? "chip !bg-emerald-700/10 !text-emerald-700 !border-emerald-700/30"
                      : "chip"}>
                      {v.validation_passed ? t("st_manufacturing_checked") : t("preview_only")}
                    </span>
                  </div>
                  {v.price_from_aed != null && (
                    <p className="text-sm text-gold-deep">
                      {t("starting_price_label")}: {v.price_from_aed} AED
                    </p>
                  )}
                  <div className="space-y-1.5">
                    <a className="btn-primary !text-xs w-full flex items-center justify-center gap-1.5"
                       href={`/api/studio/export?text=${encodeURIComponent(live.normalized)}&variant=${v.variant_id}&item=${itemType}&format=zip`}>
                      <Download size={12} /> {t("download_all")}
                    </a>
                    <div className="flex flex-wrap gap-1.5">
                      {([["pair", "PNG ×2"], ["png", "PNG macro"], ["svg", "SVG"],
                         ["svg_mirrored", "SVG mirror"], ["dxf", "DXF"],
                         ["vector_pdf", "PDF vector"], ["technical_pdf", "PDF tech"],
                         ["pdf", t("sheet_pdf")]] as const).map(([fmt, label]) => (
                        <a key={fmt} className="chip hover:border-gold-deep"
                           href={`/api/studio/export?text=${encodeURIComponent(live.normalized)}&variant=${v.variant_id}&item=${itemType}&format=${fmt}`}>
                          <Download size={10} className="inline me-1" />{label}
                        </a>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {intent && conceptState === "failed" && (
            <p className="text-[10px] text-stone-400">{t("concept_failed")}</p>
          )}
          <p className="text-[10px] text-stone-400">{t("live_note")}</p>
        </section>
      )}

      {!DEMO && (
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
                        {projSvgs[v.variant_id] ? (
                          <div className="w-full [&_svg]:w-full [&_svg]:h-auto">
                            <JewelPreview svgText={projSvgs[v.variant_id]}
                                          material="silver_925" finish="black_enamel"
                                          size="100%" />
                          </div>
                        ) : (
                          <img
                            src={authedUrl(`/api/design/projects/${p.id}/variants/${v.variant_id}.svg`)}
                            alt={v.meta.label_en}
                            className="w-full aspect-square bg-white rounded border border-stone-100"
                          />
                        )}
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
      )}
    </div>
  );
}
