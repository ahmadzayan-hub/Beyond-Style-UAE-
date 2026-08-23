/**
 * Client-side mirror of the server pricing engine, driven entirely by the
 * rules JSON served from /api/design/pricing. The showroom screen uses this
 * for instant interactivity; the server's design.quote records the
 * authoritative quote (with provenance) when staff confirm.
 */

export interface PricingRules {
  currency: string;
  price_floor_aed: number;
  policy_note_en: string;
  policy_note_ar: string;
  base_by_item: Record<string, number>;
  material_multiplier: Record<
    string,
    { label_en: string; label_ar: string; factor: number | null; quote_on_request?: boolean }
  >;
  finish_adder: Record<string, { label_en: string; label_ar: string; aed: number }>;
  variant_factor: Record<string, number>;
  per_letter_after: { letters_included: number; aed_per_letter: number };
  quantity_tiers: { min_qty: number; factor: number }[];
}

export interface PriceEstimate {
  quoteOnRequest: boolean;
  unitAed?: number;
  totalAed?: number;
}

export function estimatePrice(
  rules: PricingRules,
  itemType: string,
  variantId: string,
  letterCount: number,
  material: string,
  finish: string,
  quantity: number,
): PriceEstimate {
  const base = rules.base_by_item[itemType];
  const mat = rules.material_multiplier[material];
  const fin = rules.finish_adder[finish];
  if (base === undefined || !mat || !fin) return { quoteOnRequest: true };
  if (mat.quote_on_request || mat.factor === null) return { quoteOnRequest: true };

  const vfac = rules.variant_factor[variantId] ?? 1.0;
  const extraLetters = Math.max(0, letterCount - rules.per_letter_after.letters_included);
  let unit = base * mat.factor * vfac + fin.aed + extraLetters * rules.per_letter_after.aed_per_letter;

  const qty = Math.max(1, quantity);
  const tier = [...rules.quantity_tiers].sort((a, b) => b.min_qty - a.min_qty)
    .find((t) => qty >= t.min_qty);
  unit *= tier?.factor ?? 1.0;
  unit = Math.max(unit, rules.price_floor_aed);
  unit = Math.round(unit / 5) * 5;
  return { quoteOnRequest: false, unitAed: unit, totalAed: unit * qty };
}
