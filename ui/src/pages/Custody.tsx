import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileCheck2, Flag, Inbox, TimerReset } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Asset, Licence } from "../api";
import { useT } from "../i18n";

const ORIGIN_BADGE: Record<string, string> = {
  supplier_authorised: "supplier",
  business_discovery: "discovery",
  manual_inbox: "inbox",
  workshop_photograph: "workshop",
  ai_generated: "AI",
};

export default function Custody() {
  const t = useT();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const reviewFilter = params.get("review") ?? "";
  const [licenceId, setLicenceId] = useState("");

  const assets = useQuery({
    queryKey: ["assets", reviewFilter],
    queryFn: () =>
      api.get<{ assets: Asset[] }>(`/api/assets${reviewFilter ? `?review_state=${reviewFilter}` : ""}`),
  });
  const licences = useQuery({
    queryKey: ["licences"],
    queryFn: () => api.get<{ licences: Licence[] }>("/api/licences"),
  });
  const inbox = useQuery({
    queryKey: ["inbox"],
    queryFn: () => api.get<{ pending: string[]; count: number }>("/api/inbox"),
    refetchInterval: 10000,
  });

  const ingest = useMutation({
    mutationFn: () => api.post("/api/ingest/inbox", { licence_id: licenceId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
    },
  });

  const queues = [
    { key: "mark_review", label: "marks", icon: Flag },
    { key: "duplicate_review", label: "near-dupes", icon: AlertTriangle },
    { key: "resolution_review", label: "low-res", icon: TimerReset },
  ];

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <h2 className="font-display text-2xl">{t("custody")}</h2>
        <div className="flex items-center gap-2 text-sm">
          <Inbox size={15} className="text-stone-400" />
          <span>{inbox.data?.count ?? 0} pending</span>
          <input
            className="border border-stone-300 rounded px-2 py-1 text-sm w-36"
            placeholder="licence id"
            value={licenceId}
            onChange={(e) => setLicenceId(e.target.value)}
          />
          <button
            className="btn-primary"
            disabled={!licenceId || !(inbox.data?.count ?? 0) || ingest.isPending}
            onClick={() => ingest.mutate()}
          >
            {t("ingest_inbox")}
          </button>
        </div>
      </header>
      {ingest.error && <p className="text-deny text-sm">{String(ingest.error)}</p>}

      <section className="card p-4">
        <h3 className="font-display text-sm mb-3 flex items-center gap-2">
          <FileCheck2 size={15} /> {t("licences")}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(licences.data?.licences ?? []).map((l) => (
            <div key={l.id} className={`border rounded p-3 text-sm ${l.expired ? "border-deny/50" : l.expiring_soon ? "border-amber-flag/50" : "border-stone-200"}`}>
              <div className="font-medium">{l.id}</div>
              <div className="text-stone-500 text-xs">{l.licensor}</div>
              <div className="text-xs mt-1">
                scope: {l.scope} ·{" "}
                <b className={l.expired ? "text-deny" : l.expiring_soon ? "text-amber-flag" : "text-ok"}>
                  {l.expired ? "expired" : `${l.days_left}d left`}
                </b>
              </div>
            </div>
          ))}
          {!licences.data?.licences.length && <p className="text-stone-400 text-sm">—</p>}
        </div>
      </section>

      <section>
        <div className="flex gap-2 mb-3">
          <button className={`chip ${!reviewFilter ? "!border-accent !text-accent" : ""}`} onClick={() => setParams({})}>
            all
          </button>
          {queues.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className={`chip ${reviewFilter === key ? "!border-accent !text-accent" : ""}`}
              onClick={() => setParams({ review: key })}
            >
              <Icon size={11} /> {label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {(assets.data?.assets ?? []).map((a) => (
            <figure key={a.id} className="card overflow-hidden">
              <img src={`/api/assets/${a.id}/file`} alt={a.filename} className="aspect-square object-cover w-full" loading="lazy" />
              <figcaption className="p-2 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="chip">{ORIGIN_BADGE[a.origin] ?? a.origin}</span>
                  {a.review_state !== "clear" && (
                    <Flag size={12} className="text-amber-flag" aria-label={a.review_state} />
                  )}
                </div>
                <div className="text-stone-400 truncate">{a.source_handle || a.filename}</div>
                <div className="text-stone-400">{a.licence_id ?? "—"}</div>
              </figcaption>
            </figure>
          ))}
        </div>
        {!assets.data?.assets.length && (
          <p className="text-stone-400 text-sm mt-4">
            Drop files into <code>library/inbox/</code>, create a licence, then ingest.
          </p>
        )}
      </section>
    </div>
  );
}
