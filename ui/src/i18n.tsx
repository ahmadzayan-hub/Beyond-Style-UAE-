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
