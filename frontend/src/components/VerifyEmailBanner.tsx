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
      <div className="mb-6 rounded-md bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
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
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-900 bg-amber-950/40 px-3 py-2 text-sm text-amber-200">
      <span>
        Verify <span className="font-medium">{user.email}</span> so signing in with GitHub reaches
        this account instead of creating a second one.
      </span>
      {sent ? (
        <span className="text-amber-300/80">Verification email sent.</span>
      ) : (
        <button
          onClick={handleResend}
          disabled={resend.isPending}
          className="rounded-md border border-amber-800 px-3 py-1 text-amber-200 hover:bg-amber-900/40 disabled:opacity-50"
        >
          {resend.isPending ? "Sending…" : "Resend email"}
        </button>
      )}
      {failed && <span className="w-full text-red-300">{failed}</span>}
    </div>
  );
}
