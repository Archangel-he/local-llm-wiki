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
    await expect(page.getByText("Graph view")).toBeVisible();
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

    await page.getByRole("tab", { name: "搜索" }).click();
    await page.getByLabel("筛选文件").fill("orphan");
    await expect(page.getByTestId("tree-item-lint-orphan")).toBeVisible();
    await expect(page.getByTestId("tree-item-raw-a")).toBeHidden();
  });

  test("submits the deterministic mock question for every scope", async ({
    page,
  }) => {
    await page.getByLabel("问答范围").selectOption("workspace");
    await page.getByLabel("输入问题").fill("Aurora 什么时候启动？");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByTestId("mock-answer")).toContainText("2025-03-01");
    await expect(page.getByTestId("mock-answer")).toContainText("aurora-a.md");
    await expect(
      page.getByRole("button", { name: "Save to Wiki" }),
    ).toBeVisible();
  });

  test("keeps API keys write-only", async ({ page }) => {
    await page.getByTestId("model-settings-trigger").click();
    await page
      .getByRole("tab", { name: "OpenAI-compatible API" })
      .click();
    await page.getByTestId("api-key-input").fill("e2e-secret-value");
    await page.getByRole("button", { name: "Save credential" }).click();
    await expect(page.getByTestId("api-key-input")).toHaveValue("");
    await expect(page.getByTestId("credential-state")).toContainText(
      "cannot be read",
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

    await page.getByRole("button", { name: "放大" }).click();
    await page.getByRole("button", { name: "缩小" }).click();
    await page.getByRole("button", { name: "重置视图" }).click();
    await page.getByRole("button", { name: "打开图谱设置" }).click();
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
      .getByRole("button", { name: "Preview Obsidian export" })
      .click();
    await expect(page.getByTestId("export-preview")).toContainText(
      "Obsidian Vault export preview",
    );
    await expect(page.getByTestId("export-preview")).toContainText("aliases:");
  });

  test("creates, tests and activates a custom model profile", async ({
    page,
  }) => {
    await page.getByTestId("model-settings-trigger").click();
    await expect(
      page.getByTestId("model-profile-list").locator("article"),
    ).toHaveCount(1);
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await expect(
      page.getByTestId("model-profile-list").locator("article"),
    ).toHaveCount(2);
    await page
      .getByRole("tab", { name: "OpenAI-compatible API" })
      .click();
    await page.getByTestId("api-key-input").fill("e2e-secret-value");
    await page
      .getByLabel(
        "I understand source content may be sent to this external endpoint.",
      )
      .check();
    await page
      .getByRole("button", { name: "Save credential and create profile" })
      .click();

    const profile = page
      .locator('[data-testid^="model-profile-profile-"]')
      .filter({ hasText: "Remote API" });
    await expect(profile).toContainText("Remote API");
    await profile.getByRole("button", { name: "Test", exact: true }).click();
    await expect(profile).toContainText("active");
    await profile.getByRole("button", { name: "Set default" }).click();
    await expect(profile.getByRole("button", { name: "Default" })).toBeDisabled();
    await expect(page.locator("body")).not.toContainText("e2e-secret-value");
  });
});
