import { defineTool } from "eve/tools";
import { z } from "zod";

import { apiGet } from "../lib/api";
import type { RepoOut } from "../lib/types";
import { actingAs } from "../lib/schema";

export default defineTool({
  description:
    "List the repositories tracked by the platform, each with its latest analysis id and status. Start here when the user names a repository but not an analysis.",
  inputSchema: z.object({}),
  async execute(_input, ctx) {
    const repos = await apiGet<RepoOut[]>("/api/repos", { actingAs: actingAs(ctx) });
    return {
      count: repos.length,
      repositories: repos.map((repo) => ({
        id: repo.id,
        slug: `${repo.owner}/${repo.name}`,
        url: repo.url,
        default_branch: repo.default_branch,
        latest_analysis_id: repo.latest_analysis_id,
        latest_analysis_status: repo.latest_analysis_status,
      })),
    };
  },
});
