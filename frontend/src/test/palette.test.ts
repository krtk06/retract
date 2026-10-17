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

const PICO8 = new Set([
  "#000000", "#1D2B53", "#7E2553", "#008751", "#AB5236", "#5F574F", "#C2C3C7",
  "#FFF1E8", "#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#83769C",
  "#FF77A8", "#FFCCAA",
]);

describe("palette", () => {
  it("assigns a colour to every pillar in both themes, from the PICO-8 set", () => {
    for (const pillar of PILLARS) {
      for (const theme of ["dark", "light"] as const) {
        expect(PICO8.has(colorFor(PILLAR_COLOR_VAR[pillar], theme))).toBe(true);
      }
    }
  });

  it("assigns a colour to every severity in both themes, from the PICO-8 set", () => {
    for (const severity of SEVERITIES) {
      for (const theme of ["dark", "light"] as const) {
        expect(PICO8.has(colorFor(SEVERITY_COLOR_VAR[severity], theme))).toBe(true);
      }
    }
  });

  it("assigns a colour to every run status in both themes", () => {
    for (const status of ["pending", "running", "done", "failed"] as const) {
      for (const theme of ["dark", "light"] as const) {
        expect(PICO8.has(colorFor(STATUS_COLOR_VAR[status], theme))).toBe(true);
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
    expect(colorFor("var(--nope)", "dark")).toBe("#000000");
  });
});
