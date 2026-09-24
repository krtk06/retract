const STYLES: Record<string, string> = {
  pending: "bg-zinc-700 text-zinc-200",
  running: "bg-blue-900 text-blue-200",
  done: "bg-emerald-900 text-emerald-200",
  failed: "bg-red-900 text-red-200",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status] ?? STYLES.pending}`}
    >
      {status}
    </span>
  );
}
