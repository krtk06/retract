import { defineSandbox } from "eve/sandbox";
import { JustBashSandbox } from "eve/sandbox/just-bash";

/**
 * The agent does no code execution of its own: analysis runs server-side in the
 * Python service, and every fact comes back through the API tools. A sandbox is
 * still required (eve's built-in file tools use it), so this uses just-bash: a
 * pure-JavaScript shell that needs neither a container runtime nor a VM, which
 * keeps `eve dev`, `eve eval`, and CI working on hosts without Docker.
 *
 * Shared by the root agent and every subagent — subagents do not inherit a
 * parent's sandbox, so each one re-exports this from its `sandbox.ts`.
 */
export const environment = JustBashSandbox.environment();

export const openSandbox = defineSandbox(() => environment.open());

export default openSandbox;
