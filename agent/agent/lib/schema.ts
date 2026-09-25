import type { ToolContext } from "eve/tools";
import { z } from "zod";

/** The id every analysis-scoped tool takes. */
export const analysisId = z.number().int().positive().describe("Analysis id from get_analysis");

/** A symbol name or dotted module path, e.g. "authenticate" or "pkg.auth". */
export const symbolName = z
  .string()
  .min(1)
  .max(200)
  .describe('Symbol name or dotted module path, e.g. "authenticate" or "pkg.auth"');

/**
 * The login (or numeric id) the eve session is acting as, so API calls are
 * attributed to the human who started the conversation rather than to a
 * shared service account.
 */
export function actingAs(ctx: ToolContext): string | undefined {
  const principal = ctx.session.auth.current ?? ctx.session.auth.initiator;
  return principal?.principalId;
}
