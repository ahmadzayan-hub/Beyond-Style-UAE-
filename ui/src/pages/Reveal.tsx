import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, Instagram, MessageCircle, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, authedUrl, DesignProjectDetail } from "../api";
import { useLang, useT } from "../i18n";
import { estimatePrice, PricingRules } from "../pricing";

/**
 * Showroom "Design Reveal" — the customer-facing screen used in the studio
 * (and on the customer's phone) to support the buying decision. Everything
 * is live and client-side: material/finish switching recolors the verified
 * vector, prices update instantly from the served pricing rules, and the
 * WhatsApp CTA carries the exact configuration. The trust ladder stays
 * visible: an AI concept can never present itself as production-approved.
 */

const INSTAGRAM_URL = "https://www.instagram.com/beyond.style.uae";
const WHATSAPP_NUMBER = "971555615509"; // Beyond Style UAE business WhatsApp

const MATERIALS = ["silver_925", "gold_plated", "rose_gold_plated", "oxidized_silver", "solid_gold_18k"] as const;
const FINISHES = ["black_enamel", "white_enamel", "mirror_polish", "brushed"] as const;

const METAL_STOPS: Record<string, [string, string, string]> = {
  silver_925: ["#f4f4f6", "#c9cbd1", "#9a9da6"],
  gold_plated: ["#f5e3b8", "#d9b979", "#a5813f"],
  rose_gold_plated: ["#f6d9cd", "#e0ac98", "#b97d67"],
  oxidized_silver: ["#a9abb2", "#6f7178", "#3c3d42"],
  solid_gold_18k: ["#f7e6bb", "#ddbd7c", "#aa8542"],
};

function JewelPreview({ svgText, material, finish, size }: {
  svgText: string; material: string; finish: string; size: number;
}) {
  const { art, face } = useMemo(() => {
    const inner = svgText.slice(svgText.indexOf(">") + 1, svgText.lastIndexOf("</svg>"));
    // face diameter comes from the artwork's own mm viewBox (item-dependent)
    const vb = svgText.match(/viewBox="0 0 ([\d.]+)/);
    return {
      art: inner.replace(/<circle[^>]*\/>/g, ""),
      face: vb ? parseFloat(vb[1]) : 20,
    };
  }, [svgText]);
  const c = face / 2;
  const [hi, mid, lo] = METAL_STOPS[material] ?? METAL_STOPS.silver_925;
  const enamel = finish === "black_enamel" ? "#131315"
    : finish === "white_enamel" ? "#f5f2ec" : null;
  const gid = `m-${material}`;
  // On enamel: raised metal lettering. On plain metal: engraved dark lettering.
  const artFill = enamel ? `url(#${gid})` : finish === "brushed" ? "#3a3b40" : "#26262b";
  const faceFill = enamel ?? mid;
  return (
    <svg viewBox={`0 0 ${face} ${face}`} width={size} height={size}
         style={{ transition: "all .4s" }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={hi} />
          <stop offset="0.55" stopColor={mid} />
          <stop offset="1" stopColor={lo} />
        </linearGradient>
        <radialGradient id={`face-${gid}`} cx="0.35" cy="0.3" r="0.9">
          <stop offset="0" stopColor={enamel ? faceFill : hi} />
          <stop offset="1" stopColor={enamel ? faceFill : mid} />
        </radialGradient>
      </defs>
      <style>{`.reveal-art path { fill: ${artFill}; transition: fill .4s; }`}</style>
      <circle cx={c} cy={c} r={c * 0.98} fill={`url(#${gid})`} />
      <circle cx={c} cy={c} r={c * 0.87} fill={`url(#face-${gid})`} />
      {enamel === "#f5f2ec" && (
        <circle cx={c} cy={c} r={c * 0.87} fill="none" stroke="#ddd8cd"
                strokeWidth={face * 0.004} />
      )}
      <g className="reveal-art" dangerouslySetInnerHTML={{ __html: art }} />
      <ellipse cx={c * 0.68} cy={c * 0.56} rx={c * 0.46} ry={c * 0.22} fill="#ffffff"
               opacity={enamel ? 0.08 : 0.28}
               transform={`rotate(-24 ${c * 0.68} ${c * 0.56})`} />
    </svg>
  );
}

export default function Reveal() {
  const t = useT();
  const { lang } = useLang();
  const { id } = useParams();
  const [search] = useSearchParams();
  // /reveal/live?text=… presents a LIVE composition straight from the
  // deterministic serverless pipeline — no stored project needed.
  const liveText = id === "live" ? (search.get("text") ?? "") : "";
  const liveItem = search.get("item") ?? "cufflink";
  const projectId = Number(id === "live" ? 0 : (id ?? 1));

  const project = useQuery({
    queryKey: ["design-project", projectId],
    queryFn: () => api.get<DesignProjectDetail>(`/api/design/projects/${projectId}`),
    enabled: !liveText,
  });
  const liveQuery = useQuery({
    queryKey: ["studio-live", liveText, liveItem],
    queryFn: async () => {
      const res = await fetch(
        `/api/studio/preview?text=${encodeURIComponent(liveText)}&item=${liveItem}`);
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    enabled: !!liveText,
  });
  const pricing = useQuery({
    queryKey: ["design-pricing"],
    queryFn: () => api.get<{ rules: PricingRules }>("/api/design/pricing"),
  });

  const [variantId, setVariantId] = useState("manufacturing_optimized");
  const [material, setMaterial] = useState("silver_925");
  const [finish, setFinish] = useState("black_enamel");
  const [quantity, setQuantity] = useState(1);
  const [stage, setStage] = useState(0); // 0 letters → 1 calligraphy → 2 product
  const [svgs, setSvgs] = useState<Record<string, string>>({});

  const p: DesignProjectDetail | undefined = liveText
    ? (liveQuery.data && {
        id: 0,
        inscription: liveQuery.data.normalized,
        normalized_inscription: liveQuery.data.normalized,
        item_type: liveQuery.data.item ?? liveItem,
        status: liveQuery.data.status,
        selected_variant: (liveQuery.data.variants ?? []).find(
          (v: { validation_passed: boolean }) => v.validation_passed)?.variant_id ?? "",
        created_at: "",
        frame: {},
        letter_sequence: liveQuery.data.letter_sequence,
        verification: liveQuery.data.verification,
        variants: liveQuery.data.variants ?? [],
        validations: {},
        approver: "",
        export_manifest: {},
      })
    : project.data;
  const rules = pricing.data?.rules;
  const variant = p?.variants.find((v) => v.variant_id === variantId) ?? p?.variants[0];

  useEffect(() => {
    if (!p) return;
    p.variants.forEach((v) => {
      const inline = (v as { svg?: string }).svg;
      if (inline) {
        setSvgs((prev) => (prev[v.variant_id] ? prev : { ...prev, [v.variant_id]: inline }));
        return;
      }
      const url = authedUrl(`/api/design/projects/${p.id}/variants/${v.variant_id}.svg`);
      fetch(url).then((r) => r.text()).then((txt) =>
        setSvgs((prev) => ({ ...prev, [v.variant_id]: txt })));
    });
  }, [p]);

  useEffect(() => {
    fetch("/api/studio/health").catch(() => {});  // warm the live pipeline
    const t1 = setTimeout(() => setStage(1), 1600);
    const t2 = setTimeout(() => setStage(2), 3200);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  const price = rules && p && variant
    ? estimatePrice(rules, p.item_type, variant.variant_id,
        p.letter_sequence.filter((l) => l.char.trim()).length,
        material, finish, quantity)
    : null;

  const matMeta = rules?.material_multiplier[material];
  const finMeta = rules?.finish_adder[finish];

  const whatsappHref = useMemo(() => {
    if (!p || !variant) return "#";
    const priceTxt = price?.quoteOnRequest
      ? (lang === "ar" ? "السعر حسب سعر السوق" : "price on request")
      : `${price?.totalAed} AED`;
    const msg = lang === "ar"
      ? `مرحباً Beyond Style! أعجبني تصميم «${p.inscription}» — ${variant.meta.label_ar}، ${matMeta?.label_ar ?? material}، ${finMeta?.label_ar ?? finish}، الكمية ${quantity}. السعر الابتدائي ${priceTxt}. أود المتابعة.`
      : `Hello Beyond Style! I love the "${p.inscription}" design — ${variant.meta.label_en}, ${matMeta?.label_en ?? material}, ${finMeta?.label_en ?? finish}, qty ${quantity}. Starting price ${priceTxt}. I'd like to proceed.`;
    return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(msg)}`;
  }, [p, variant, material, finish, quantity, price, lang, matMeta, finMeta]);

  // Reaction chips are real controls: each one changes the configuration.
  const reactions: { key: string; apply: () => void }[] = [
    { key: "rx_luxurious", apply: () => { setVariantId("luxury_diwani_jali"); setMaterial("gold_plated"); } },
    { key: "rx_simpler", apply: () => setVariantId("manufacturing_optimized") },
    { key: "rx_readable", apply: () => setVariantId("balanced_diwani") },
    { key: "rx_thicker", apply: () => setVariantId("manufacturing_optimized") },
    { key: "rx_silver", apply: () => { setMaterial("silver_925"); setFinish("black_enamel"); } },
    { key: "rx_no_enamel", apply: () => setFinish("mirror_polish") },
  ];

  if (!p) {
    return <div className="min-h-screen bg-ink text-stone-200 flex items-center justify-center">…</div>;
  }

  const ladder = p.status === "workshop_approved" ? 4
    : p.status === "manufacturing_checked" ? 3
    : p.status === "variants_composed" ? 2
    : p.status === "typography_verified" ? 1 : 0;

  return (
    <div className="min-h-screen bg-ink text-stone-100 flex flex-col">
      {/* top bar */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-stone-500/20">
        <Link to="/design" className="text-stone-400 hover:text-gold flex items-center gap-1.5 text-xs">
          <ArrowLeft size={14} /> {t("back_studio")}
        </Link>
        <div className="text-center">
          <p className="font-display tracking-[0.25em] text-gold text-sm">BEYOND STYLE</p>
          <p className="text-[9px] text-stone-400 tracking-[0.3em] uppercase">{t("design_reveal")}</p>
        </div>
        <a href={INSTAGRAM_URL} target="_blank" rel="noreferrer"
           className="text-stone-400 hover:text-gold"><Instagram size={16} /></a>
      </header>

      <main className="flex-1 w-full max-w-5xl mx-auto px-4 py-5 grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* stage */}
        <section className="lg:col-span-3 flex flex-col items-center">
          <div className="relative w-full max-w-[420px] aspect-square rounded-2xl
                          bg-gradient-to-b from-stone-500/10 to-transparent
                          border border-gold/20 flex items-center justify-center overflow-hidden">
            {stage === 0 && (
              <div dir="rtl" className="flex gap-3">
                {p.letter_sequence.map((l, i) => (
                  <span key={i}
                        className="text-5xl sm:text-6xl font-light animate-pulse"
                        style={{ animationDelay: `${i * 0.18}s`, color: "#C5A059" }}>
                    {l.char}
                  </span>
                ))}
              </div>
            )}
            {stage === 1 && variant && svgs[variant.variant_id] && (
              <div className="w-3/4 transition-transform duration-700 scale-100"
                   style={{ filter: "invert(0.92) sepia(0.35) saturate(2.2) hue-rotate(-15deg)" }}
                   dangerouslySetInnerHTML={{ __html: svgs[variant.variant_id] }} />
            )}
            {stage === 2 && variant && svgs[variant.variant_id] && (
              <div className="transition-all duration-700">
                <JewelPreview svgText={svgs[variant.variant_id]} material={material}
                              finish={finish} size={340} />
              </div>
            )}
            <button onClick={() => setStage(0)}
                    className="absolute bottom-3 end-3 text-stone-500 hover:text-gold"
                    aria-label="replay">
              <RotateCcw size={15} />
            </button>
            {stage < 2 && (
              <button onClick={() => setStage(2)}
                      className="absolute bottom-3 start-3 text-[10px] text-stone-500 hover:text-gold">
                {t("skip_reveal")}
              </button>
            )}
          </div>

          {/* trust ladder — always visible to the customer */}
          <div className="flex flex-wrap justify-center gap-1.5 mt-4">
            {(["st_typography_verified", "st_variants_composed", "st_manufacturing_checked",
               "st_workshop_approved"] as const).map((key, i) => (
              <span key={key}
                    className={`text-[10px] px-2.5 py-1 rounded-full border ${
                      i < ladder
                        ? "border-gold/50 text-gold"
                        : "border-stone-500/30 text-stone-500"
                    }`}>
                {i < ladder && <BadgeCheck size={10} className="inline me-1" />}
                {t(key)}
              </span>
            ))}
          </div>
          <p className="text-[10px] text-stone-500 mt-2 text-center max-w-sm">{t("reveal_disclaimer")}</p>
        </section>

        {/* controls + pricing */}
        <section className="lg:col-span-2 space-y-4">
          <div>
            <p dir="rtl" className="text-3xl text-gold font-light">{p.inscription}</p>
            <p className="text-xs text-stone-400 mt-1">
              {t(`item_${p.item_type}`)} · {variant?.meta[lang === "ar" ? "label_ar" : "label_en"]}
            </p>
          </div>

          {/* variant tabs */}
          <div className="flex gap-1.5 flex-wrap">
            {p.variants.map((v) => (
              <button key={v.variant_id}
                      onClick={() => setVariantId(v.variant_id)}
                      className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                        variantId === v.variant_id
                          ? "border-gold bg-gold/10 text-gold"
                          : "border-stone-500/40 text-stone-400 hover:border-gold/50"
                      }`}>
                {v.meta[lang === "ar" ? "label_ar" : "label_en"]}
              </button>
            ))}
          </div>

          {/* material switcher */}
          <div>
            <p className="text-[10px] uppercase tracking-widest text-stone-500 mb-1.5">{t("material")}</p>
            <div className="flex gap-2 flex-wrap">
              {MATERIALS.map((m) => (
                <button key={m} onClick={() => setMaterial(m)}
                        className={`w-9 h-9 rounded-full border-2 transition-all ${
                          material === m ? "border-gold scale-110" : "border-stone-500/40"
                        }`}
                        title={rules?.material_multiplier[m]?.[lang === "ar" ? "label_ar" : "label_en"] ?? m}
                        style={{ background: `linear-gradient(135deg, ${METAL_STOPS[m][0]}, ${METAL_STOPS[m][2]})` }} />
              ))}
            </div>
          </div>

          {/* finish switcher */}
          <div>
            <p className="text-[10px] uppercase tracking-widest text-stone-500 mb-1.5">{t("finish")}</p>
            <div className="flex gap-1.5 flex-wrap">
              {FINISHES.map((f) => (
                <button key={f} onClick={() => setFinish(f)}
                        className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                          finish === f
                            ? "border-gold bg-gold/10 text-gold"
                            : "border-stone-500/40 text-stone-400 hover:border-gold/50"
                        }`}>
                  {rules?.finish_adder[f]?.[lang === "ar" ? "label_ar" : "label_en"] ?? f}
                </button>
              ))}
            </div>
          </div>

          {/* price card */}
          <div className="rounded-xl border border-gold/30 bg-gold/5 p-4 space-y-2">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-stone-500">{t("starting_price_label")}</p>
                {price?.quoteOnRequest ? (
                  <p className="text-xl text-gold mt-0.5">{t("quote_on_request")}</p>
                ) : (
                  <p className="text-3xl text-gold font-light mt-0.5">
                    {price?.unitAed?.toLocaleString()} <span className="text-sm">AED</span>
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button className="w-8 h-8 rounded-full border border-stone-500/40 text-stone-300"
                        onClick={() => setQuantity((q) => Math.max(1, q - 1))}>−</button>
                <span className="text-sm w-6 text-center">{quantity}</span>
                <button className="w-8 h-8 rounded-full border border-stone-500/40 text-stone-300"
                        onClick={() => setQuantity((q) => q + 1)}>+</button>
              </div>
            </div>
            {!price?.quoteOnRequest && quantity > 1 && (
              <p className="text-xs text-stone-400">
                {t("total")}: <span className="text-gold">{price?.totalAed?.toLocaleString()} AED</span>
              </p>
            )}
            <p className="text-[10px] text-stone-500">
              {lang === "ar" ? rules?.policy_note_ar : rules?.policy_note_en}
            </p>
          </div>

          {/* reactions */}
          <div>
            <p className="text-[10px] uppercase tracking-widest text-stone-500 mb-1.5 flex items-center gap-1">
              <Sparkles size={11} /> {t("tune_design")}
            </p>
            <div className="flex gap-1.5 flex-wrap">
              {reactions.map((r) => (
                <button key={r.key} onClick={r.apply}
                        className="text-xs px-3 py-1.5 rounded-full border border-stone-500/40
                                   text-stone-300 hover:border-gold/60 hover:text-gold transition-colors">
                  {t(r.key)}
                </button>
              ))}
            </div>
          </div>

          {/* CTA */}
          <a href={whatsappHref} target="_blank" rel="noreferrer"
             className="flex items-center justify-center gap-2 w-full py-3 rounded-xl
                        bg-gold text-ink font-medium text-sm hover:bg-gold-soft transition-colors">
            <MessageCircle size={16} /> {t("continue_whatsapp")}
          </a>
        </section>
      </main>

      <footer className="text-center text-[10px] text-stone-500 pb-4">
        <a href={INSTAGRAM_URL} target="_blank" rel="noreferrer" className="hover:text-gold">
          @beyond.style.uae
        </a>
      </footer>
    </div>
  );
}
