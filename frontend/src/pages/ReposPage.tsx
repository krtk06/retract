import { useState } from "react";
import { m } from "motion/react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAnalyzeRepo, useCreateRepo, useRepos } from "../api/hooks";
import { Icon } from "../components/Icon";
import { Reveal } from "../components/Reveal";
import { StatusPill } from "../components/StatusPill";
import { EASE, stagger } from "../lib/motion";

export function ReposPage() {
  const navigate = useNavigate();
  const repos = useRepos(true);
  const createRepo = useCreateRepo();
  const analyzeRepo = useAnalyzeRepo();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const repo = await createRepo.mutateAsync(url.trim());
      setUrl("");
      const analysis = await analyzeRepo.mutateAsync(repo.id);
      navigate(`/analyses/${analysis.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    }
  }

  async function handleAnalyze(repoId: number) {
    setError(null);
    try {
      const analysis = await analyzeRepo.mutateAsync(repoId);
      navigate(`/analyses/${analysis.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    }
  }

  return (
    <div className="space-y-10">
      <h1 className="sr-only">Repositories</h1>

      <Reveal>
        <section>
          <div className="mb-4">
            <h2 className="text-xl font-semibold tracking-tight text-ink">Analyze a repository</h2>
          </div>
          <form onSubmit={handleSubmit} className="panel p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <input
                type="text"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
                className="input flex-1 font-mono"
                required
              />
              <button
                type="submit"
                disabled={createRepo.isPending || analyzeRepo.isPending}
                className="btn btn--primary sheen press"
              >
                {createRepo.isPending || analyzeRepo.isPending ? "Starting…" : "Analyze"}
              </button>
            </div>
          </form>
          {error && (
            <p className="mt-3 rounded-[2px] border border-danger/40 bg-danger-soft px-4 py-2.5 text-[13px] text-danger">
              {error}
            </p>
          )}
        </section>
      </Reveal>

      <Reveal delay={0.06}>
        <section>
          <div className="mb-4 flex items-end justify-between gap-4">
            <h2 className="text-xl font-semibold tracking-tight text-ink">Your repositories</h2>
            {repos.data && repos.data.length > 0 && (
              <span className="text-[11px] text-faint tabular-nums">{repos.data.length} tracked</span>
            )}
          </div>

          {repos.isLoading && <p className="text-[13px] text-muted">Loading…</p>}
          {repos.data?.length === 0 && (
            <p className="text-[13px] text-faint">No repositories yet — add one above.</p>
          )}

          <ul className="space-y-2.5">
            {repos.data?.map((repo, index) => (
              <m.li
                key={repo.id}
                className="card card--hover lift flex items-center gap-4 p-3.5"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.34, ease: EASE, delay: stagger(index, 0.05, 0.3) }}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-ink">
                    {repo.owner}/{repo.name}
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-faint">
                    <Icon name="repo" size={12} />
                    {repo.default_branch}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {repo.latest_analysis_status && (
                    <button
                      onClick={() => navigate(`/analyses/${repo.latest_analysis_id}`)}
                      title="View latest analysis"
                      aria-label="View latest analysis"
                    >
                      <StatusPill status={repo.latest_analysis_status} />
                    </button>
                  )}
                  <button
                    onClick={() => handleAnalyze(repo.id)}
                    disabled={analyzeRepo.isPending}
                    className="btn btn--ghost press"
                  >
                    Analyze
                  </button>
                </div>
              </m.li>
            ))}
          </ul>
        </section>
      </Reveal>
    </div>
  );
}
