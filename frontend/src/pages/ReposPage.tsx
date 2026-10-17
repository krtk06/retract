import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAnalyzeRepo, useCreateRepo, useRepos } from "../api/hooks";
import { StatusPill } from "../components/StatusPill";

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

      <section>
        <div className="mb-4">
          <p className="px-eyebrow">New analysis</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">Analyze a repository</h2>
        </div>
        <form onSubmit={handleSubmit} className="px-frame">
          <div className="px-frame flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
            <input
              type="text"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://github.com/owner/repo"
              className="px-input flex-1"
              required
            />
            <button
              type="submit"
              disabled={createRepo.isPending || analyzeRepo.isPending}
              className="px-btn px-btn--primary"
            >
              {createRepo.isPending || analyzeRepo.isPending ? "Starting…" : "Analyze"}
            </button>
          </div>
        </form>
        {error && (
          <p className="mt-3 border border-danger/25 bg-danger-soft px-4 py-2.5 text-sm text-danger">
            {error}
          </p>
        )}
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="px-eyebrow">Inventory</p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight">Your repositories</h2>
          </div>
          {repos.data && repos.data.length > 0 && (
            <span className="text-xs text-faint tabular-nums">{repos.data.length} tracked</span>
          )}
        </div>

        {repos.isLoading && <p className="text-sm text-muted">Loading…</p>}
        {repos.data?.length === 0 && (
          <p className="text-sm text-faint">No repositories yet — add one above.</p>
        )}

        <ul className="space-y-2.5">
          {repos.data?.map((repo) => (
            <li key={repo.id} className="px-card px-card-hover flex items-center gap-4 px-4 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">
                  {repo.owner}/{repo.name}
                </p>
                <p className="mt-0.5 font-mono text-xs text-faint">{repo.default_branch}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {repo.latest_analysis_status && (
                  <button
                    onClick={() => navigate(`/analyses/${repo.latest_analysis_id}`)}
                    className="transition-transform duration-300 ease-step hover:-translate-y-0.5"
                    title="View latest analysis"
                  >
                    <StatusPill status={repo.latest_analysis_status} />
                  </button>
                )}
                <button
                  onClick={() => handleAnalyze(repo.id)}
                  disabled={analyzeRepo.isPending}
                  className="px-btn px-btn--ghost"
                >
                  Analyze
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
