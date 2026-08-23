import { useMemo } from "react";

/**
 * Realistic on-screen render of the FINISHED piece, built live from the
 * verified vector: metal rim, enamel or metal face, raised-metal or
 * engraved lettering. This is what the customer (and owner) should see
 * first — the final design, not a technical outline.
 */

export const METAL_STOPS: Record<string, [string, string, string]> = {
  silver_925: ["#f4f4f6", "#c9cbd1", "#9a9da6"],
  gold_plated: ["#f5e3b8", "#d9b979", "#a5813f"],
  rose_gold_plated: ["#f6d9cd", "#e0ac98", "#b97d67"],
  oxidized_silver: ["#a9abb2", "#6f7178", "#3c3d42"],
  solid_gold_18k: ["#f7e6bb", "#ddbd7c", "#aa8542"],
};

export function JewelPreview({ svgText, material, finish, size }: {
  svgText: string; material: string; finish: string; size: number | string;
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
  const gid = `m-${material}-${finish}`;
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
      <style>{`.jewel-art-${gid.replace(/[^a-z0-9-]/gi, "")} path { fill: ${artFill}; transition: fill .4s; }`}</style>
      <circle cx={c} cy={c} r={c * 0.98} fill={`url(#${gid})`} />
      <circle cx={c} cy={c} r={c * 0.87} fill={`url(#face-${gid})`} />
      {enamel === "#f5f2ec" && (
        <circle cx={c} cy={c} r={c * 0.87} fill="none" stroke="#ddd8cd"
                strokeWidth={face * 0.004} />
      )}
      <g className={`jewel-art-${gid.replace(/[^a-z0-9-]/gi, "")}`}
         dangerouslySetInnerHTML={{ __html: art }} />
      <ellipse cx={c * 0.68} cy={c * 0.56} rx={c * 0.46} ry={c * 0.22} fill="#ffffff"
               opacity={enamel ? 0.08 : 0.28}
               transform={`rotate(-24 ${c * 0.68} ${c * 0.56})`} />
    </svg>
  );
}
