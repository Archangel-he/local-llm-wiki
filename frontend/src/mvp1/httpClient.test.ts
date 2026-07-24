import { afterEach, describe, expect, it, vi } from "vitest";
import { HttpMvp1Client } from "./httpClient";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HttpMvp1Client", () => {
  it("maps the real MVP1 tree, source, Wiki, activity and graph contracts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input);
        if (url.endsWith("/tree")) {
          return json({
            sources: [{ id: "source-1", filename: "brief.md", status: "active" }],
            wiki: [{ id: "page-1", title: "Brief", page_type: "topic" }],
          });
        }
        if (url.endsWith("/jobs")) return json({ items: [] });
        if (url.endsWith("/graph")) {
          return json({
            nodes: [
              { id: "page-1", label: "Brief", type: "topic", degree: 1 },
              { id: "page-2", label: "Lin", type: "entity", degree: 1 },
            ],
            edges: [
              {
                id: "edge-1",
                source: "page-1",
                target: "page-2",
                target_slug: "lin",
                type: "citation",
              },
            ],
          });
        }
        if (url.endsWith("/wiki-system/activity")) {
          return json({
            items: [
              {
                id: "activity-1",
                action: "wiki.committed",
                resource_type: "wiki_page",
                resource_id: "page-1",
                created_at: "2026-07-24T08:00:00Z",
                metadata: { job_id: "job-1" },
              },
            ],
          });
        }
        if (url.endsWith("/sources/source-1/content")) {
          return new Response("# Brief\n\nRaw content");
        }
        if (url.endsWith("/sources/source-1")) {
          return json({
            id: "source-1",
            filename: "brief.md",
            sha256: "abc123",
            status: "active",
            created_at: "2026-07-24T08:00:00Z",
          });
        }
        if (url.endsWith("/wiki/page-1")) {
          return json({
            id: "page-1",
            slug: "brief",
            title: "Brief",
            page_type: "topic",
            summary: "A source summary.",
            status: "current",
            revision_no: 1,
            markdown: "# Brief\n\nLinks to [[Lin]].",
            aliases: ["briefing"],
            links: [
              {
                target_page_id: "page-2",
                target_slug: "lin",
                type: "wikilink",
              },
            ],
            citations: [
              {
                source_id: "source-1",
                locator: "paragraph:1",
                excerpt: "Raw content",
              },
            ],
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    const data = await new HttpMvp1Client("", "workspace-1").loadWorkspace();

    expect(data.sources[0]).toMatchObject({
      filename: "brief.md",
      content: "# Brief\n\nRaw content",
    });
    expect(data.pages.find((page) => page.id === "page-1")).toMatchObject({
      type: "concept",
      aliases: ["briefing"],
      sources: ["source-1 · paragraph:1 · Raw content"],
    });
    expect(data.graphEdges[0]).toMatchObject({ type: "citation" });
    expect(data.pages.find((page) => page.systemView === "index")?.body).toEqual([
      "- [[Brief]] · topic",
    ]);
    expect(data.activity[0]?.pageId).toBe("page-1");
  });

  it("uses the server error envelope without exposing response internals", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(
          {
            error: {
              code: "MODEL_PROFILE_INVALID",
              message: "The profile is unavailable.",
              details: { internal: "must not be surfaced" },
            },
          },
          409,
        ),
      ),
    );

    await expect(
      new HttpMvp1Client("", "workspace-1").setDefaultModelProfile("profile-1"),
    ).rejects.toMatchObject({
      code: "MODEL_PROFILE_INVALID",
      message: "The profile is unavailable.",
    });
  });

  it("creates and restores a downloadable Vault export", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/exports")) {
        return json({
          id: "export-1",
          status: "queued",
          progress: { stage: "queued" },
          error: null,
          filename: null,
          sha256: null,
          size_bytes: null,
        });
      }
      if (url.endsWith("/exports/export-1")) {
        return json({
          id: "export-1",
          status: "completed",
          progress: { stage: "completed" },
          error: null,
          filename: "vault.zip",
          sha256: "export-sha",
          size_bytes: 1024,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const client = new HttpMvp1Client("", "workspace-1");
    await expect(client.createExport()).resolves.toMatchObject({
      id: "export-1",
      status: "queued",
    });
    await expect(client.getExport("export-1")).resolves.toMatchObject({
      status: "completed",
      filename: "vault.zip",
      sha256: "export-sha",
      sizeBytes: 1024,
    });
    expect(client.getExportDownloadUrl("export-1")).toBe(
      "/api/workspaces/workspace-1/exports/export-1/download",
    );
  });
});
