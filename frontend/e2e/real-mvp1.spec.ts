import { expect, test } from "@playwright/test";

test.skip(
  process.env.MVP1_REAL_API !== "true",
  "Requires the real Compose MVP1 stack.",
);

test("uses the real MVP1 API from upload through Wiki refresh", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByTestId("file-tree")).toContainText("aurora-a.md");
  await expect(page.getByTestId("file-tree")).toContainText("Project Aurora");
  await expect(page.getByTestId("graph-panel")).toHaveAttribute(
    "data-node-count",
    /^[1-9]\d*$/,
  );
  await expect(page.locator(".model-status")).toContainText("Mock LLM · mock");

  await page.getByTestId("source-upload-input").setInputFiles(
    "../tests/fixtures/aurora-b.md",
  );
  await expect(page.getByTestId("job-status")).toContainText("completed", {
    timeout: 15_000,
  });
  await expect(page.getByTestId("file-tree")).toContainText("aurora-b.md");
  await page
    .getByTestId("file-tree")
    .getByRole("button", { name: "aurora-b.md", exact: true })
    .click();
  await expect(page.getByTestId("wiki-title")).toHaveText("aurora-b.md");
  await expect(page.getByTestId("wiki-panel")).toContainText(
    "Postponed to: 2025-04-15",
  );
});
