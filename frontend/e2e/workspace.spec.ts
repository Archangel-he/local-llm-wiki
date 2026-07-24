import { expect, test } from "@playwright/test";

test.describe("Obsidian-style workspace", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("loads the complete workspace and fixed graph fixture", async ({
    page,
  }) => {
    await expect(page.getByTestId("workspace")).toBeVisible();
    await expect(page.getByTestId("file-tree")).toBeVisible();
    await expect(page.getByTestId("graph-panel")).toBeVisible();
    await expect(page.getByTestId("query-panel")).toBeVisible();
    await expect(page.getByTestId("wiki-panel")).toBeVisible();
    await expect(page.locator(".workspace-heading")).toHaveText(
      "Knowledge graph",
    );
    await expect(
      page
        .frameLocator('[data-testid="graph-repro-frame"]')
        .locator("#graph"),
    ).toBeVisible();
    await expect(page.getByTestId("graph-panel")).toHaveAttribute(
      "data-node-count",
      "4",
    );
    await expect(page.getByTestId("graph-panel")).toHaveAttribute(
      "data-edge-count",
      "2",
    );
  });

  test("links both the file tree and graph nodes to the inspector", async ({
    page,
  }) => {
    await page.getByTestId("tree-item-wiki-entities").click();
    await expect(page.getByTestId("wiki-title")).toHaveText("Lin");
    await expect(
      page
        .frameLocator('[data-testid="graph-repro-frame"]')
        .locator("#graph"),
    ).toHaveAttribute("data-selected-node", "node-b");

    await page
      .getByTestId("graph-node-node-d")
      .evaluate((element: HTMLButtonElement) => element.click());
    await expect(page.getByTestId("wiki-title")).toHaveText("Orphan Note");
    await page.getByRole("tab", { name: "Backlinks" }).click();
    await expect(page.getByTestId("wiki-panel")).toContainText(
      "This page is an orphan",
    );
  });

  test("expands, collapses, and filters the logical file tree", async ({
    page,
  }) => {
    const wikiSection = page.getByTestId("tree-section-wiki");
    await expect(wikiSection).toHaveAttribute("aria-expanded", "true");
    await wikiSection.click();
    await expect(wikiSection).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("tree-item-wiki-entities")).toBeHidden();
    await wikiSection.click();
    await expect(page.getByTestId("tree-item-wiki-entities")).toBeVisible();

    await page.getByLabel("Filter files...").fill("orphan");
    await expect(page.getByTestId("tree-item-lint-orphan")).toBeVisible();
    await expect(page.getByTestId("tree-item-raw-a")).toBeHidden();
  });

  test("shows the selected model without presenting a fake answer", async ({
    page,
  }) => {
    await expect(page.getByText("LLM Wiki answer")).toBeVisible();
    await expect(page.getByTestId("query-model")).toContainText(
      "Local Ollama · qwen3:8b",
    );
    await page.getByLabel("Answer scope").selectOption("workspace");
    await page
      .getByLabel("Ask about this knowledge space...")
      .fill("When did Aurora start?");
    await page
      .getByTestId("query-panel")
      .getByRole("button", { name: "Ask", exact: true })
      .click();
    await expect(page.getByTestId("query-notice")).toContainText(
      "does not run a real query yet",
    );
    await expect(page.getByTestId("query-notice")).not.toContainText(
      "2025-03-01",
    );
  });

  test("keeps API keys write-only", async ({ page }) => {
    await page.getByTestId("model-settings-trigger").click();
    await page.getByTestId("api-key-input").fill("e2e-secret-value");
    await page
      .getByRole("button", { name: "Connect & load models" })
      .click();
    await page
      .getByLabel(
        "I understand source content may be sent to this external endpoint.",
      )
      .check();
    await page
      .getByRole("button", { name: "Save configuration" })
      .click();
    await expect(page.getByTestId("api-key-input")).toHaveValue("");
    await expect(page.getByTestId("credential-state")).toContainText(
      "never displayed",
    );
    await expect(page.locator("body")).not.toContainText("e2e-secret-value");
  });

  test("shows degraded LLM health without blocking the Wiki", async ({
    page,
  }) => {
    await page.getByTestId("health-trigger").click();
    await expect(page.getByTestId("health-llm")).toContainText("degraded");
    await expect(page.getByTestId("wiki-panel")).toBeVisible();
    await page.getByTestId("tree-item-wiki-concepts").click();
    await expect(page.getByTestId("wiki-title")).toHaveText("Knowledge Graph");
  });

  test("keeps graph controls usable after pane resizing", async ({ page }) => {
    const leftHandle = page.getByTestId("left-resizer");
    const initialLeft = Number(await leftHandle.getAttribute("aria-valuenow"));
    const leftBox = await leftHandle.boundingBox();
    if (!leftBox) throw new Error("Left resize handle is not visible");
    await page.mouse.move(
      leftBox.x + leftBox.width / 2,
      leftBox.y + leftBox.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      leftBox.x + leftBox.width / 2 + 32,
      leftBox.y + leftBox.height / 2,
      { steps: 5 },
    );
    await page.mouse.up();
    await expect(leftHandle).toHaveAttribute(
      "aria-valuenow",
      String(initialLeft + 32),
    );

    const queryHandle = page.getByTestId("query-resizer");
    const initialQuery = Number(
      await queryHandle.getAttribute("aria-valuenow"),
    );
    const queryBox = await queryHandle.boundingBox();
    if (!queryBox) throw new Error("Query resize handle is not visible");
    await page.mouse.move(
      queryBox.x + queryBox.width / 2,
      queryBox.y + queryBox.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      queryBox.x + queryBox.width / 2,
      queryBox.y + queryBox.height / 2 - 28,
      { steps: 5 },
    );
    await page.mouse.up();
    await expect(queryHandle).toHaveAttribute(
      "aria-valuenow",
      String(initialQuery + 28),
    );

    await page.getByRole("button", { name: "Zoom in" }).click();
    await page.getByRole("button", { name: "Zoom out" }).click();
    await page.getByRole("button", { name: "Fit graph" }).click();
    await page.getByRole("button", { name: "Controls" }).click();
    await page.getByRole("button", { name: "Reheat layout" }).click();
    await expect(
      page
        .frameLocator('[data-testid="graph-repro-frame"]')
        .locator("#graph"),
    ).toBeVisible();
  });

  test("ingests Markdown into the tree, Wiki, graph and system views", async ({
    page,
  }) => {
    await page.getByTestId("source-upload-input").setInputFiles({
      name: "aurora-brief.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(
        "# Aurora Brief\n\nA source note linked to [[Project Aurora]].",
      ),
    });

    await expect(page.getByTestId("job-status")).toContainText("completed", {
      timeout: 3_000,
    });
    await expect(page.getByTestId("graph-panel")).toHaveAttribute(
      "data-node-count",
      "5",
    );
    await expect(page.getByTestId("graph-panel")).toHaveAttribute(
      "data-edge-count",
      "3",
    );
    const renderedGraph = page
      .frameLocator('[data-testid="graph-repro-frame"]')
      .locator("#graph");
    await expect(renderedGraph).toHaveAttribute("data-node-count", "5");
    await expect(renderedGraph).toHaveAttribute("data-edge-count", "3");
    await page
      .getByTestId("file-tree")
      .getByRole("button", { name: "Aurora Brief", exact: true })
      .click();
    await expect(page.getByTestId("wiki-title")).toHaveText("Aurora Brief");
    await expect(page.getByTestId("wiki-panel")).toContainText(
      "Project Aurora",
    );

    await page.getByRole("button", { name: "Index", exact: true }).click();
    await expect(page.getByTestId("wiki-panel")).toContainText("Aurora Brief");
    await expect(page.getByTestId("wiki-panel")).toContainText(
      "Read-only system view",
    );
    await page.getByRole("button", { name: "Activity", exact: true }).click();
    await expect(page.getByTestId("wiki-panel")).toContainText(
      "aurora-brief.md ingested",
    );

    await page
      .getByRole("button", { name: "Export", exact: true })
      .click();
    await expect(page.getByTestId("export-preview")).toContainText(
      "Obsidian Vault export preview",
    );
    await expect(page.getByTestId("export-preview")).toContainText("aliases:");
    await page.getByRole("button", { name: "Create Vault ZIP" }).click();
    await expect(page.getByTestId("export-status")).toContainText("completed");
    await expect(page.getByTestId("export-download")).toBeVisible();
    await page.getByRole("button", { name: "Close export preview" }).click();
    await page.reload();
    await page
      .getByRole("button", { name: "Export", exact: true })
      .click();
    await expect(page.getByTestId("export-download")).toBeVisible();
  });

  test("creates, tests and activates a custom model profile", async ({
    page,
  }) => {
    await page.getByTestId("model-settings-trigger").click();
    await expect(
      page.getByTestId("model-profile-list").locator("article"),
    ).toHaveCount(1);
    await page.getByTestId("api-key-input").fill("e2e-secret-value");
    await page
      .getByRole("button", { name: "Connect & load models" })
      .click();
    await expect(page.getByText("2 models available")).toBeVisible();
    const modelSelect = page.getByLabel("Model ID");
    await expect(modelSelect.locator("option")).toHaveCount(2);
    await modelSelect.selectOption("deepseek-v4-pro");
    await page
      .getByLabel(
        "I understand source content may be sent to this external endpoint.",
      )
      .check();
    await page
      .getByRole("button", { name: "Save configuration" })
      .click();

    const profile = page
      .locator('[data-testid^="model-profile-profile-"]')
      .filter({ hasText: "DeepSeek" });
    await expect(profile).toContainText("deepseek-v4-pro");
    await profile.getByRole("button", { name: "Test", exact: true }).click();
    await expect(profile).toContainText("Ready");
    await profile.getByRole("button", { name: "Use model" }).click();
    await expect(profile.getByRole("button", { name: "Default" })).toBeDisabled();

    await profile.getByRole("button", { name: "Edit" }).click();
    await page.getByLabel("Model ID").fill("deepseek-v4-flash");
    await page
      .getByRole("button", { name: "Update configuration" })
      .click();
    await expect(
      page.getByTestId("model-profile-list").locator("article"),
    ).toHaveCount(2);
    await expect(profile).toContainText("deepseek-v4-flash");
    await expect(profile).toContainText("Not tested");
    await expect(page.locator("body")).not.toContainText("e2e-secret-value");

    page.once("dialog", (dialog) => dialog.accept());
    await profile.getByRole("button", { name: "Delete" }).click();
    await expect(
      page.getByTestId("model-profile-list").locator("article"),
    ).toHaveCount(1);
    await expect(page.getByRole("status")).toContainText("was deleted");
  });

  test("switches the interface between English and Chinese", async ({
    page,
  }) => {
    await page.getByTestId("model-settings-trigger").click();
    await page.getByTestId("language-select").selectOption("zh");
    await expect(page.getByRole("button", { name: "资料库" })).toBeVisible();
    await expect(page.locator(".workspace-heading")).toHaveText("知识图谱");
    await page.getByTestId("language-select").selectOption("en");
    await expect(page.getByRole("button", { name: "Library" })).toBeVisible();
    await expect(page.locator(".workspace-heading")).toHaveText(
      "Knowledge graph",
    );
  });
});
