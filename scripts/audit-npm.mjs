#!/usr/bin/env node
/**
 * `npm audit`, with a documented allow-list.
 *
 * `npm audit --audit-level=high` cannot express "fail on new advisories at or above
 * high, except this known one". A repository that has a single unfixable transitive
 * high therefore gets a job that is red forever — which is worse than having no job
 * at all, because people learn to ignore it, and then ignore the real finding too.
 *
 * This fails on anything at or above the threshold that is not explicitly allowed,
 * and prints both the allowed exceptions and the clean bill of health, so the
 * exceptions stay visible instead of silent.
 *
 * Usage: node scripts/audit-npm.mjs <dir> [threshold] [-- npm audit flags]
 *   node scripts/audit-npm.mjs frontend high --omit=dev
 */

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const SEVERITY_ORDER = ["info", "low", "moderate", "high", "critical"];

// package name -> why it is allowed. Keep the reason specific; a vague entry here
// is how a real advisory gets hidden.
const ALLOWED = new Map([
  [
    "undici",
    "transitive through `eve`, which pins it in both frontend and agent; the only " +
      "fix npm offers is a breaking downgrade of eve itself. Undici is a Node HTTP " +
      "client, so it is not in the browser bundle at all. Revisit when eve ships a " +
      "patched undici.",
  ],
]);

const [dir = ".", threshold = "high", ...npmFlags] = process.argv.slice(2);
if (!existsSync(join(dir, "package.json"))) {
  console.error(`audit-npm: no package.json in ${dir}`);
  process.exit(2);
}
const minimum = SEVERITY_ORDER.indexOf(threshold);
if (minimum === -1) {
  console.error(`audit-npm: unknown threshold "${threshold}"`);
  process.exit(2);
}

function runAudit() {
  const args = ["audit", "--json", ...npmFlags];
  try {
    return JSON.parse(execFileSync("npm", args, { cwd: dir, encoding: "utf8", maxBuffer: 1 << 26 }));
  } catch (error) {
    // `npm audit` exits non-zero as soon as it finds anything; the JSON it printed is
    // still the report we want. A non-zero exit with no stdout is a real error.
    if (typeof error.stdout === "string" && error.stdout.trim()) {
      return JSON.parse(error.stdout);
    }
    throw error;
  }
}

const report = runAudit();
const vulnerabilities = report.vulnerabilities ?? {};

const blocking = [];
const allowedSeen = [];
for (const [name, detail] of Object.entries(vulnerabilities)) {
  if (SEVERITY_ORDER.indexOf(detail.severity) < minimum) continue;
  const advisories = (detail.via ?? [])
    .map((entry) => (typeof entry === "string" ? entry : entry.title))
    .filter(Boolean);
  if (ALLOWED.has(name)) {
    allowedSeen.push({ name, line: `${detail.severity} ${name}: ${advisories.join("; ")}` });
  } else {
    blocking.push(`${detail.severity} ${name}: ${advisories.join("; ")}`);
  }
}

for (const { name, line } of allowedSeen) {
  console.log(`allow-listed  ${line}`);
  console.log(`              -> ${ALLOWED.get(name)}`);
}
if (blocking.length > 0) {
  console.error(`\nnpm audit found ${blocking.length} blocking vulnerabilit(ies) in ${dir}:`);
  for (const line of blocking) console.error(`  ${line}`);
  process.exit(1);
}
console.log(`${dir}: no vulnerabilities at or above "${threshold}" beyond the allow-list`);
