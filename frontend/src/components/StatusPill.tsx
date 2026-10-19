import { Icon, type IconName } from "./Icon";
import { STATUS_COLOR_VAR, type RunStatus } from "../lib/palette";

const FALLBACK: RunStatus = "pending";

const GLYPHS: Record<RunStatus, IconName> = {
  pending: "clock",
  running: "activity",
  done: "check",
  failed: "x",
};

/**
 * The verdict stamp. Status is never colour alone: the word and the glyph are
 * always present, and a running analysis carries an assistive-only live note
 * rather than a pulse the layout does not otherwise show.
 */
export function StatusPill({ status }: { status: string }) {
  const key = (status in STATUS_COLOR_VAR ? status : FALLBACK) as RunStatus;
  const color = `var(${STATUS_COLOR_VAR[key]})`;
  const live = key === "running";

  return (
    <span className="stamp" style={{ color }}>
      <Icon name={GLYPHS[key]} size={11} />
      {status}
      {live && (
        <span aria-hidden="true" className="sr-only">
          (live)
        </span>
      )}
    </span>
  );
}
