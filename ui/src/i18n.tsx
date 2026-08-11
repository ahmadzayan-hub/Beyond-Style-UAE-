/** Bilingual EN/AR with proper RTL. Equivalent meaning, not literal translation. */

import { createContext, useContext, useEffect, useState } from "react";

export type Lang = "en" | "ar";

const STRINGS: Record<string, { en: string; ar: string }> = {
  custody: { en: "Custody", ar: "الحفظ والرخص" },
  corpus: { en: "Corpus", ar: "المكتبة التحليلية" },
  trends: { en: "Trends", ar: "الاتجاهات" },
  studio: { en: "Studio", ar: "الاستوديو" },
  workshop: { en: "Workshop", ar: "الورشة" },
  policy_feed: { en: "Policy feed", ar: "سجل القواعد" },
  assets: { en: "Assets", ar: "الأصول" },
  licences: { en: "Licences", ar: "الرخص" },
  ingest_inbox: { en: "Ingest inbox", ar: "معالجة صندوق الوارد" },
  review_queue: { en: "Review queues", ar: "قوائم المراجعة" },
  corpus_health: { en: "Corpus health", ar: "جاهزية المكتبة" },
  references: { en: "references", ar: "مرجعًا" },
  sources: { en: "sources", ar: "مصدرًا" },
  floor_blocked: {
    en: "Synthesis is blocked until the corpus floor is met (P4).",
    ar: "التحليل متوقف حتى تكتمل أرضية المكتبة (القاعدة ٤).",
  },
  whitespace: { en: "Whitespace", ar: "الفرص غير المطروقة" },
  whitespace_lead: {
    en: "Rare combinations of established elements. A combination seen 40 times is a saturated market, not an instruction.",
    ar: "تركيبات نادرة من عناصر راسخة. التركيبة المتكررة أربعين مرة سوقٌ مشبعة لا وصفةٌ للتقليد.",
  },
  draft_brief: { en: "Draft brief from this", ar: "أنشئ موجزًا من هذه" },
  frequency: { en: "Frequency", ar: "التكرار" },
  cooccurrence: { en: "Co-occurrence", ar: "الاقتران" },
  briefs: { en: "Briefs", ar: "الموجزات" },
  provenance: { en: "Provenance", ar: "الإسناد" },
  promote: { en: "Promote", ar: "اعتماد" },
  generate: { en: "Generate", ar: "توليد" },
  concept_only: { en: "CONCEPT ONLY", ar: "تصور أولي فقط" },
  gate_passed: { en: "Gate passed", ar: "اجتاز البوابة" },
  gate_rejected: { en: "Rejected", ar: "مرفوض" },
  specs: { en: "Spec cards", ar: "بطاقات التصنيع" },
  upload_photo: { en: "Upload workshop photograph", ar: "رفع صورة القطعة المصنعة" },
  export: { en: "Export", ar: "تصدير" },
  export_note: {
    en: "Workshop photographs only. Every export writes MANIFEST.csv.",
    ar: "صور الورشة فقط. كل تصدير يكتب ملف MANIFEST.csv.",
  },
  escalations: { en: "Decisions needed", ar: "قرارات معلقة" },
  approve: { en: "Approve", ar: "موافقة" },
  reject: { en: "Reject", ar: "رفض" },
  starting_price: { en: "Starting price (AED)", ar: "السعر الابتدائي (درهم)" },
  price_note: {
    en: "All prices are starting prices, confirmed with the customer on WhatsApp.",
    ar: "جميع الأسعار ابتدائية وتُؤكد مع العميل عبر واتساب.",
  },
  open_questions: { en: "Open questions", ar: "أسئلة معلقة" },
  nearest_refs: { en: "Nearest references", ar: "أقرب المراجع" },
  similarity: { en: "similarity", ar: "تشابه" },
  command: { en: "Command", ar: "مركز القيادة" },
  advisory: { en: "advisory", ar: "استرشادي" },
  advisory_gate_note: {
    en: "Gate ran on the development embedder — treat this pass as advisory until CLIP is installed and tuned.",
    ar: "عملت البوابة على نموذج تطويري — اعتبر هذا الاجتياز استرشاديًا حتى تثبيت CLIP ومعايرته.",
  },
  confirm_ingest: {
    en: "Ingest {n} file(s) from the inbox under this licence?",
    ar: "معالجة {n} ملفًا من صندوق الوارد بموجب هذه الرخصة؟",
  },
  confirm_export: {
    en: "Export {n} workshop photograph(s) to the catalogue?",
    ar: "تصدير {n} صورة ورشة إلى الكتالوج؟",
  },
  confirm_reject: {
    en: "Reject this escalation? The decision is recorded in the ledger.",
    ar: "رفض هذا التصعيد؟ يُسجل القرار في السجل.",
  },
  token_title: { en: "API token required", ar: "مطلوب رمز الدخول" },
  token_hint: {
    en: "Paste the token from var/api-token.txt (or BSOS_API_TOKEN). It stays in this browser.",
    ar: "الصق الرمز من var/api-token.txt (أو BSOS_API_TOKEN). يبقى في هذا المتصفح.",
  },
  connect: { en: "Connect", ar: "اتصال" },
  compose_brief: { en: "Compose brief", ar: "إنشاء موجز" },
  pending: { en: "pending", ar: "قيد الانتظار" },
  no_items: { en: "Nothing here yet.", ar: "لا شيء هنا بعد." },
  core_label: { en: "Orchestrator core", ar: "نواة التنسيق" },
  synapse_load: { en: "Synapse load", ar: "حمل الاشتباك" },
  synapse_sub: { en: "kernel tool-call activity, last 100 ledger events", ar: "نشاط استدعاءات الأدوات، آخر ١٠٠ حدث" },
  coherence: { en: "Quantum coherence", ar: "التماسك الكمي" },
  coherence_sub: { en: "corpus readiness vs the P4 floor", ar: "جاهزية المكتبة مقابل أرضية القاعدة ٤" },
  intelligence_stream: { en: "Intelligence stream", ar: "بث الاستخبارات" },
  upload_avatar: { en: "photo", ar: "صورة" },
  open_decisions: { en: "open decisions", ar: "قرارات معلقة" },
  design_studio: { en: "Design Studio", ar: "استوديو التصميم" },
  design_studio_lead: {
    en: "Names are shaped and verified letter-by-letter by a deterministic typography engine — spelling is never trusted to an image model, and only validated, human-approved vectors become workshop files.",
    ar: "تُشكَّل الأسماء وتُدقَّق حرفًا حرفًا بمحرك خطوط حتمي — لا يُعهد بالإملاء إلى نموذج صور أبدًا، ولا تتحول إلى ملفات ورشة إلا المتجهات المدقّقة المعتمدة بشريًا.",
  },
  new_inscription: { en: "New inscription", ar: "نقش جديد" },
  verify_spelling: { en: "Verify spelling", ar: "تدقيق الإملاء" },
  spelling_note: {
    en: "Verification is structural: HarfBuzz shaping with the approved font, then a glyph-by-glyph check against the expected letter sequence. Failures route to human review.",
    ar: "التدقيق بنيوي: تشكيل هارفبز بالخط المعتمد ثم مطابقة كل محرف مع تسلسل الحروف المتوقع. أي إخفاق يُحال لمراجعة بشرية.",
  },
  projects: { en: "Projects", ar: "المشاريع" },
  pick_project: { en: "Select a project to see its variants and trust ladder.", ar: "اختر مشروعًا لعرض نسخه وسلّم الثقة." },
  compose_variants: { en: "Compose 3 calligraphic variants", ar: "توليد ٣ نسخ خطية" },
  validate_mfg: { en: "Validate manufacturing", ar: "تحقق تصنيعي" },
  approve_workshop: { en: "Approve for workshop", ar: "اعتماد للورشة" },
  workshop_package: { en: "Workshop file package", ar: "حزمة ملفات الورشة" },
  export_package: { en: "Produce workshop files (SVG · DXF · PDF · PNG)", ar: "إنتاج ملفات الورشة (SVG · DXF · PDF · PNG)" },
  approval_id: { en: "Approval ID", ar: "معرّف الاعتماد" },
  package_note: {
    en: "Vector files are in millimetres. Illustrator-compatible SVG/PDF — no native .AI file is claimed. AI concept imagery is never a production file.",
    ar: "ملفات المتجهات بالمليمتر. SVG/PDF متوافقة مع Illustrator — دون ادعاء ملف ‎.AI أصلي. صور التصور الأولي ليست ملفات إنتاج أبدًا.",
  },
  expert_review: { en: "calligrapher review advised", ar: "يُنصح بمراجعة خطاط" },
  st_typography_verified: { en: "typography verified", ar: "إملاء مدقّق" },
  st_variants_composed: { en: "variants composed", ar: "نسخ مولّدة" },
  st_manufacturing_checked: { en: "manufacturing checked", ar: "تحقق تصنيعي" },
  st_workshop_approved: { en: "workshop approved", ar: "معتمد للورشة" },
  st_human_review: { en: "human review required", ar: "تلزم مراجعة بشرية" },
  item_cufflink: { en: "Cufflink", ar: "زر كم" },
  item_pendant: { en: "Pendant", ar: "قلادة" },
  item_bracelet: { en: "Bracelet", ar: "سوار" },
  item_ring: { en: "Ring", ar: "خاتم" },
  item_brooch: { en: "Brooch", ar: "بروش" },
  item_coin: { en: "Coin / medallion", ar: "عملة / ميدالية" },
  item_corporate_gift: { en: "Corporate gift", ar: "هدية مؤسسية" },
  design_reveal: { en: "Design Reveal", ar: "كشف التصميم" },
  back_studio: { en: "Studio", ar: "الاستوديو" },
  skip_reveal: { en: "skip", ar: "تخطي" },
  present_customer: { en: "Present to customer", ar: "عرض على العميل" },
  material: { en: "Material", ar: "المعدن" },
  finish: { en: "Finish", ar: "التشطيب" },
  starting_price_label: { en: "Starting price", ar: "السعر الابتدائي" },
  quote_on_request: { en: "Priced on request", ar: "السعر عند الطلب" },
  total: { en: "Total", ar: "الإجمالي" },
  tune_design: { en: "Tune the design", ar: "عدّل التصميم" },
  rx_luxurious: { en: "More luxurious", ar: "أكثر فخامة" },
  rx_simpler: { en: "Simpler", ar: "أبسط" },
  rx_readable: { en: "Easier to read", ar: "أسهل قراءة" },
  rx_thicker: { en: "Thicker letters", ar: "حروف أسمك" },
  rx_silver: { en: "Classic silver", ar: "فضي كلاسيكي" },
  rx_no_enamel: { en: "No enamel", ar: "بدون مينا" },
  continue_whatsapp: { en: "Continue on WhatsApp", ar: "المتابعة عبر واتساب" },
  suggest_arabic: { en: "Suggest Arabic spelling", ar: "اقتراح الكتابة بالعربية" },
  confirm_spelling_flag: { en: "confirm spelling", ar: "أكد الإملاء" },
  suggestion_note: {
    en: "Suggestions come from a curated name dictionary (or a flagged letter-mapping guess) — never from an image model. The confirmed Arabic is still verified letter-by-letter.",
    ar: "الاقتراحات من قاموس أسماء منسق (أو تقريب حرفي مُعلَّم) — وليست من نموذج صور أبدًا. النص العربي المؤكد يُدقق حرفًا حرفًا.",
  },
  preview_only: { en: "preview", ar: "معاينة" },
  generating: { en: "Shaping & verifying…", ar: "جارٍ التشكيل والتدقيق…" },
  mixed_pick: { en: "Pick one script:", ar: "اختر أحد النصين:" },
  download_all: { en: "Download all files (ZIP)", ar: "تنزيل كل الملفات (ZIP)" },
  final_design: { en: "Final design", ar: "التصميم النهائي" },
  item_type_label: { en: "Item type", ar: "نوع القطعة" },
  showcase_title: {
    en: "Type a name. See it become a real piece.",
    ar: "اكتب اسمًا، وشاهده يتحول إلى قطعة حقيقية.",
  },
  showcase_sub: {
    en: "Spelling verified letter-by-letter, three calligraphic variants, live prices, and every file ready to download.",
    ar: "إملاء مدقّق حرفًا حرفًا، ثلاث نسخ خطية، أسعار مباشرة، وكل الملفات جاهزة للتنزيل.",
  },
  fin_black_enamel: { en: "Black enamel", ar: "مينا سوداء" },
  fin_white_enamel: { en: "White enamel", ar: "مينا بيضاء" },
  fin_mirror_polish: { en: "Mirror polish", ar: "تلميع مرآة" },
  fin_brushed: { en: "Brushed", ar: "مصقول ناعم" },
  sheet_pdf: { en: "Customer sheet", ar: "ورقة العميل" },
  live_error: {
    en: "Could not generate — check the inscription (max 40 characters) and try again.",
    ar: "تعذر التوليد — تحقق من النقش (٤٠ حرفًا كحد أقصى) وأعد المحاولة.",
  },
  live_note: {
    en: "Generated live by the deterministic pipeline: real HarfBuzz shaping, structural spelling verification, geometry validation and pricing. All files are extractable; vector and technical files are marked PREVIEW until workshop approval in the full system.",
    ar: "مولّد مباشرة بالخط الحتمي: تشكيل هارفبز حقيقي، تدقيق إملائي بنيوي، تحقق هندسي وتسعير. كل الملفات قابلة للاستخراج؛ وتُعلَّم ملفات المتجهات والملفات الفنية «معاينة» حتى اعتماد الورشة في النظام الكامل.",
  },
  reveal_disclaimer: {
    en: "Preview is an approximate visualization of the verified vector artwork. Production files are released only after workshop approval.",
    ar: "المعاينة تصور تقريبي للرسم المتجهي المدقّق. تصدر ملفات الإنتاج فقط بعد اعتماد الورشة.",
  },
};

const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({
  lang: "en",
  setLang: () => {},
});

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem("bsos-lang") as Lang) || "en");
  useEffect(() => {
    localStorage.setItem("bsos-lang", lang);
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
  }, [lang]);
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>;
}

export function useLang() {
  return useContext(LangContext);
}

export function useT() {
  const { lang } = useLang();
  return (key: keyof typeof STRINGS | string): string => STRINGS[key]?.[lang] ?? String(key);
}
