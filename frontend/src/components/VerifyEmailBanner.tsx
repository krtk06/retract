import { useState } from "react";

import { ApiError } from "../api/client";
import { useMe, useResendVerification } from "../api/hooks";

/**
 * Asks the user to confirm their email address, and confirms it after they do.
 *
 * Two states matter and neither is decoration:
 *
 * - **Just verified.** The link in the email lands on the API, which redirects here
 *   with `?email_verified=1`. Without a word about it the banner would simply vanish,
 *   which reads as "that did nothing".
 * - **Not verified.** It is worth saying because verification is what lets a GitHub
 *   sign-in reach this account instead of making a second one. It is not a wall: the
 *   app works unverified, so this is a prompt, not a gate.
 */
export function VerifyEmailBanner() {
  const me = useMe();
  const resend = useResendVerification();
  const [sent, setSent] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const justVerified = new URLSearchParams(window.location.search).get("email_verified") === "1";
  const user = me.data;

  if (justVerified) {
    return (
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-ok px-panel px-4 py-3 text-ok">
        <span aria-hidden="true" className="block h-[8px] w-[8px] shrink-0 bg-ok" />
        Email verified — signing in with GitHub will now reach this account.
      </div>
    );
  }

  if (!user?.email || user.email_verified) return null;

  async function handleResend() {
    setFailed(null);
    try {
      await resend.mutateAsync();
      setSent(true);
    } catch (err) {
      setFailed(
        err instanceof ApiError ? err.message : "Could not send the email. Is the API running?",
      );
    }
  }

  return (
    <div className="anim-step-in mb-6 flex flex-wrap items-center justify-between gap-3 px-panel px-4 py-3">
      <div className="flex min-w-[16rem] flex-1 flex-col gap-1">
        <p className="font-ui text-[9px] uppercase tracking-[0.16em] text-warn">
          Verifying your email
        </p>
        <span className="text-[13px] text-ink">
          <span className="font-semibold">{user.email}</span> — signing in with GitHub reaches this
          account instead of creating a second one.
        </span>
      </div>
      {sent ? (
        <span className="text-[13px] text-muted">Verification email sent.</span>
      ) : (
        <button
          onClick={handleResend}
          disabled={resend.isPending}
          className="px-btn px-btn--ghost"
        >
          {resend.isPending ? "Sending…" : "Resend email"}
        </button>
      )}
      {failed && <span className="w-full text-danger">{failed}</span>}
    </div>
  );
}
