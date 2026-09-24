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
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-lg font-semibold">Analyze a repository</h2>
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/owner/repo"
            className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none placeholder:text-zinc-500 focus:border-zinc-500"
            required
          />
          <button
            type="submit"
            disabled={createRepo.isPending || analyzeRepo.isPending}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
          >
            {createRepo.isPending || analyzeRepo.isPending ? "Starting…" : "Analyze"}
          </button>
        </form>
        {error && (
          <p className="mt-3 rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">{error}</p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Your repositories</h2>
        {repos.isLoading && <p className="text-sm text-zinc-400">Loading…</p>}
        {repos.data?.length === 0 && (
          <p className="text-sm text-zinc-500">No repositories yet — add one above.</p>
        )}
        <ul className="space-y-2">
          {repos.data?.map((repo) => (
            <li
              key={repo.id}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium">
                  {repo.owner}/{repo.name}
                </p>
                <p className="text-xs text-zinc-500">{repo.default_branch}</p>
              </div>
              <div className="flex items-center gap-3">
                {repo.latest_analysis_status && (
                  <button
                    onClick={() => navigate(`/analyses/${repo.latest_analysis_id}`)}
                    className="hover:opacity-80"
                    title="View latest analysis"
                  >
                    <StatusPill status={repo.latest_analysis_status} />
                  </button>
                )}
                <button
                  onClick={() => handleAnalyze(repo.id)}
                  disabled={analyzeRepo.isPending}
                  className="rounded-md border border-zinc-700 px-3 py-1 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
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
