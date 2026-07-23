import { mockHealth } from "../fixtures/workspace";
import { getHealthSnapshot } from "./health";

describe("getHealthSnapshot", () => {
  it("normalizes the backend health contract for the UI", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "degraded",
          components: {
            api: "ok",
            postgres: "ok",
            redis: "ok",
            worker: "ok",
            storage: "ok",
            llm: "unavailable",
          },
        }),
      }),
    );

    const health = await getHealthSnapshot();

    expect(health.source).toBe("api");
    expect(health.overall).toBe("degraded");
    expect(health.components).toContainEqual({
      name: "llm",
      label: "LLM",
      status: "degraded",
      detail: "Unavailable",
    });
  });

  it("falls back to safe mock health when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getHealthSnapshot()).resolves.toEqual(mockHealth);
  });
});
