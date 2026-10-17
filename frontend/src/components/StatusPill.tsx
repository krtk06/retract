const STYLES: Record<string, string> = {
  pending: "border-line-strong bg-surface-2 text-muted",
  running: "border-info/30 bg-info-soft text-info",
  done: "border-ok/30 bg-ok-soft text-ok",
  failed: "border-danger/30 bg-danger-soft text-danger",
};

const DOT: Record<string, string> = {
  pending: "bg-faint",
  running: "bg-info anim-blink",
  done: "bg-ok",
  failed: "bg-danger",
};

export function StatusPill({ status }: { status: string }) {
  const style = STYLES[status] ?? STYLES.pending;
  const dot = DOT[status] ?? DOT.pending;
  return (
    <span className={`px-badge border ${style}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 ${dot}`} />
      {status}
    </span>
  );
}
