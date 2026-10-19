import { describe, expect, it } from "vitest";
import {
  PILLARS,
  PILLAR_COLOR_VAR,
  PILLAR_LABELS,
  SEVERITIES,
  SEVERITY_COLOR_VAR,
  STATUS_COLOR_VAR,
  colorFor,
  scoreTone,
} from "../lib/palette";

/** Every literal the palette is allowed to resolve to, per theme. */
const PALETTE = new Set([
  // pillar ink ladder
  "#1d1a16", "#3d3830", "#5d564c", "#7d766a", "#9d9689", "#beb7aa",
  "#ece8e1", "#c5bfb4", "#9e978b", "#7a7469", "#585349", "#3a3731",
  // severity ramp
  "#b0392c", "#9a5b08", "#7a6a2a", "#3568b8", "#6d6860",
  "#e06a5c", "#d99a3d", "#c2a04d", "#6f9ade", "#8d887e",
  // status ramp
  "#1f7a4d", "#4fb07d",
]);

describe("palette", () => {
  it("assigns a colour to every pillar in both themes, from the set", () => {
    for (const pillar of PILLARS) {
      for (const theme of ["dark", "light"] as const) {
        expect(PALETTE.has(colorFor(PILLAR_COLOR_VAR[pillar], theme))).toBe(true);
      }
    }
  });

  it("assigns a colour to every severity in both themes, from the set", () => {
    for (const severity of SEVERITIES) {
      for (const theme of ["dark", "light"] as const) {
        expect(PALETTE.has(colorFor(SEVERITY_COLOR_VAR[severity], theme))).toBe(true);
      }
    }
  });

  it("assigns a colour to every run status in both themes", () => {
    for (const status of ["pending", "running", "done", "failed"] as const) {
      for (const theme of ["dark", "light"] as const) {
        expect(PALETTE.has(colorFor(STATUS_COLOR_VAR[status], theme))).toBe(true);
      }
    }
  });

  it("uses all six pillars exactly once, in a fixed order", () => {
    expect(PILLARS).toEqual([
      "security", "code-quality", "testing", "architecture", "documentation", "dependencies",
    ]);
    expect(new Set(PILLARS).size).toBe(6);
  });

  it("labels every pillar and severity", () => {
    for (const pillar of PILLARS) expect(PILLAR_LABELS[pillar]).toBeTruthy();
    // Bare custom-property names: call sites interpolate these into
    // `var(${...})` themselves, so a pre-wrapped "var(--sev-x)" would double up.
    for (const severity of SEVERITIES) expect(SEVERITY_COLOR_VAR[severity]).toMatch(/^--/);
  });

  it("thresholds scores monotonically", () => {
    expect(scoreTone(100)).toBe("ok");
    expect(scoreTone(80)).toBe("ok");
    expect(scoreTone(79)).toBe("info");
    expect(scoreTone(60)).toBe("info");
    expect(scoreTone(59)).toBe("warn");
    expect(scoreTone(40)).toBe("warn");
    expect(scoreTone(39)).toBe("danger");
    expect(scoreTone(0)).toBe("danger");
  });

  it("resolves an unknown reference to the canvas rather than throwing", () => {
    expect(colorFor("var(--nope)", "dark")).toBe("#131210");
    expect(colorFor("var(--nope)", "light")).toBe("#faf9f7");
  });
});
