import { afterEach, describe, expect, it, vi } from "vitest";
import { MockMvp1Client } from "./mockClient";

afterEach(() => {
  vi.useRealTimers();
});

describe("MockMvp1Client", () => {
  it("validates the MVP1 source file boundary", async () => {
    const client = new MockMvp1Client();

    await expect(
      client.uploadSource(new File(["binary"], "notes.pdf")),
    ).rejects.toMatchObject({
      code: "UNSUPPORTED_FILE_TYPE",
    });

    const oversized = {
      name: "large.md",
      size: 10 * 1024 * 1024 + 1,
    } as File;
    await expect(client.uploadSource(oversized)).rejects.toMatchObject({
      code: "FILE_TOO_LARGE",
    });
  });

  it("deduplicates uploads and commits the Wiki, graph and activity atomically", async () => {
    vi.useFakeTimers();
    const client = new MockMvp1Client();
    const file = new File(
      ["# Aurora Brief\n\nLinks to [[Project Aurora]]."],
      "aurora-brief.md",
      { type: "text/markdown" },
    );

    const first = await client.uploadSource(file);
    expect(first.duplicate).toBe(false);
    expect(first.job).not.toBeNull();

    const duplicate = await client.uploadSource(file);
    expect(duplicate.duplicate).toBe(true);
    expect(duplicate.job).toBeNull();

    const completed = new Promise<void>((resolve) => {
      client.subscribeJob(first.job!.id, (event) => {
        if (event.type === "completed") resolve();
      });
    });
    await vi.advanceTimersByTimeAsync(620);
    await completed;

    const workspace = await client.loadWorkspace();
    expect(workspace.pages.some((page) => page.title === "Aurora Brief")).toBe(true);
    expect(workspace.graphEdges.at(-1)?.type).toBe("derived_from");
    expect(workspace.activity[0]?.label).toContain("aurora-brief.md");
    expect(workspace.pages.find((page) => page.systemView === "index")?.body).toContain(
      "- [[Aurora Brief]] · source",
    );
    const preview = await client.getExportPreview();
    expect(preview.files.map((file) => file.path)).toEqual(
      expect.arrayContaining(["System/index.md", "System/log.md"]),
    );
  });

  it("requires consent and a successful test before switching defaults", async () => {
    const client = new MockMvp1Client();
    const input = {
      displayName: "Remote API",
      provider: "openai_compatible" as const,
      baseUrl: "https://api.example.com/v1",
      modelName: "wiki-model",
      apiKey: "write-only-secret",
      externalTransferConfirmed: false,
    };

    await expect(client.createModelProfile(input)).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
    });

    const profile = await client.createModelProfile({
      ...input,
      externalTransferConfirmed: true,
    });
    await expect(client.setDefaultModelProfile(profile.id)).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
    });

    const active = await client.testModelProfile(profile.id);
    expect(active).toMatchObject({
      status: "active",
      latencyMs: 42,
      hasCredential: true,
    });
    await client.setDefaultModelProfile(profile.id);
    expect((await client.getModelProfiles()).defaultProfileId).toBe(profile.id);
    expect(JSON.stringify(await client.getModelProfiles())).not.toContain(
      "write-only-secret",
    );
  });
});
