import { mockHealth } from "../fixtures/workspace";
import { getHealthSnapshot } from "./health";

describe("getHealthSnapshot", () => {
  it("falls back to safe mock health when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getHealthSnapshot()).resolves.toEqual(mockHealth);
  });
});
