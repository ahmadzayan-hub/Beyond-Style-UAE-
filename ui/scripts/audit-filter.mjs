#!/usr/bin/env node
/**
 * npm audit with a documented accepted-risk list.
 *
 * Fails (exit 1) on any HIGH or CRITICAL advisory that is not explicitly
 * accepted below. Accepted entries are risk decisions, not mutes: each needs
 * a justification and should be removed the moment upstream ships a fix.
 */

import { execSync } from "node:child_process";

// GHSA-qwww-vcr4-c8h2 — react-router "RSC Mode CSRF Bypass".
//   BSOS's UI is a client-only SPA (BrowserRouter; no SSR, no React Server
//   Components, no server actions), so the vulnerable code path never runs.
//   As of 2026-07-28 the latest published react-router (7.18.1) is still
//   flagged — there is no fixed version to upgrade to. Revisit on release.
const ACCEPTED = new Set(["GHSA-qwww-vcr4-c8h2"]);

let raw;
try {
  raw = execSync("npm audit --json", { encoding: "utf8" });
} catch (err) {
  raw = err.stdout; // npm audit exits non-zero when advisories exist
}
const report = JSON.parse(raw);

const offending = [];
const accepted = [];
for (const [pkg, vuln] of Object.entries(report.vulnerabilities ?? {})) {
  if (!["high", "critical"].includes(vuln.severity)) continue;
  // Advisory objects live on the source package; transitive entries reference
  // their source by name (string) and are covered by the source's verdict.
  const advisories = (vuln.via ?? [])
    .filter((v) => typeof v === "object")
    .map((v) => ({ id: v.url?.split("/").pop() ?? "unknown", title: v.title ?? "" }));
  if (advisories.length === 0) continue;
  for (const adv of advisories) {
    (ACCEPTED.has(adv.id) ? accepted : offending).push(
      `${pkg}: ${adv.id} (${vuln.severity}) ${adv.title}`,
    );
  }
}

for (const line of accepted) console.log(`accepted-risk: ${line}`);
if (offending.length) {
  console.error("\nUnaccepted high/critical advisories:");
  for (const line of offending) console.error(`  ${line}`);
  process.exit(1);
}
console.log("npm audit: no unaccepted high/critical advisories");
