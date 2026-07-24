import { expect, test, type Locator, type Page } from "@playwright/test";

async function grabRenderedNode(page: Page, canvas: Locator) {
  const box = await canvas.boundingBox();
  if (!box) throw new Error("Reproduction canvas is not visible");

  const step = 10;
  const left = box.x + box.width * 0.12;
  const right = box.x + box.width * 0.88;
  const top = box.y + box.height * 0.12;
  const bottom = box.y + box.height * 0.88;

  for (let y = top; y <= bottom; y += step) {
    for (let x = left; x <= right; x += step) {
      await page.mouse.move(x, y);
      await page.mouse.down();
      if (await canvas.evaluate((element) => element.classList.contains("dragging"))) {
        return { x, y };
      }
      await page.mouse.up();
    }
  }

  throw new Error("No reproduction node responded to pointer drag");
}

test("moves the reproduction controls into Graph controls", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  const frame = page.frameLocator('[data-testid="graph-repro-frame"]');
  const canvas = frame.locator("#graph");
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute("data-node-count", "4");
  await expect(canvas).toHaveAttribute("data-edge-count", "2");
  await expect(canvas).toHaveAttribute("data-label-sizing", "node-relative");
  await expect(canvas).toHaveAttribute("data-label-hide-below", "4.5");
  await expect(canvas).toHaveAttribute("data-all-nodes-visible", "true");
  await expect(canvas).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(frame.locator(".panel")).toHaveCount(0);

  const initialScale = Number(await canvas.getAttribute("data-camera-scale"));
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect
    .poll(async () => Number(await canvas.getAttribute("data-camera-scale")))
    .toBeGreaterThan(initialScale);
  await page.getByRole("button", { name: "Controls" }).click();
  await page.getByLabel("Node size").fill("0.55");
  await expect(frame.locator("#node-size")).toHaveValue("0.55");
  await expect(canvas).toHaveAttribute("data-node-size", "0.55");
  await page.getByLabel("Link thickness").fill("2");
  await expect(frame.locator("#link-thickness")).toHaveValue("2");
  await expect(canvas).toHaveAttribute("data-link-thickness", "2");
  await page
    .locator("label.graph-toggle", { hasText: "Show arrows" })
    .click();
  await expect(canvas).toHaveAttribute("data-show-arrows", "true");
  await page.getByLabel("Center force").fill("0.2");
  await expect(frame.locator("#center")).toHaveValue("0.2");
  await page.getByLabel("Repel force").fill("1500");
  await expect(frame.locator("#repel")).toHaveValue("1500");
  await page.getByLabel("Link strength").fill("1.25");
  await expect(frame.locator("#link-strength")).toHaveValue("1.25");
  await page.getByLabel("Link distance").fill("220");
  await expect(frame.locator("#link-distance")).toHaveValue("220");

  await page.getByRole("button", { name: "Reheat layout" }).click();
  await expect(frame.locator("#status")).toContainText("simulation running");
  await page.getByRole("button", { name: "Reset positions" }).click();
  await expect(canvas).toHaveAttribute("data-all-nodes-visible", "true");
  await page.screenshot({
    path: testInfo.outputPath("graph-controls.png"),
    animations: "disabled",
  });
});

test("scales labels with nodes and hides them completely below the readable size", async ({
  page,
}) => {
  await page.goto("/");
  const frame = page.frameLocator('[data-testid="graph-repro-frame"]');
  const canvas = frame.locator("#graph");
  await expect(canvas).toBeVisible();

  await page.getByRole("button", { name: "Controls" }).click();
  await page.getByLabel("Node size").fill("0.45");
  for (let index = 0; index < 10; index += 1) {
    await page.getByRole("button", { name: "Zoom out" }).click();
  }

  await expect(canvas).toHaveAttribute("data-camera-scale", "0.200");
  await expect(canvas).toHaveAttribute("data-visible-label-count", "0");

  await page
    .locator('[data-testid^="graph-node-"]')
    .first()
    .click({ force: true });
  await expect(canvas).toHaveAttribute("data-focused-node", /\S+/);
  await expect(canvas).toHaveAttribute("data-visible-label-count", "0");
});

test("drags a node with the copied reproduction runtime", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  const frame = page.frameLocator('[data-testid="graph-repro-frame"]');
  const canvas = frame.locator("#graph");
  await expect(canvas).toBeVisible();
  await page.waitForTimeout(1200);

  const hit = await grabRenderedNode(page, canvas);
  await expect(canvas).toHaveAttribute("data-focused-node", /\S+/);
  const selectedNodeId = await canvas.getAttribute("data-focused-node");
  await page.mouse.up();
  await expect(canvas).not.toHaveClass(/dragging/);
  await expect(canvas).toHaveAttribute("data-focused-node", /\S+/);
  await expect(canvas).toHaveAttribute("data-focus-strength", "1.00");
  const wikiTitlesByNode: Record<string, string> = {
    "node-a": "Project Aurora",
    "node-b": "Lin",
    "node-c": "Knowledge Graph",
    "node-d": "Orphan Note",
  };
  await expect(page.getByTestId("wiki-title")).toHaveText(
    wikiTitlesByNode[selectedNodeId ?? ""],
  );
  await page.screenshot({
    path: testInfo.outputPath("copied-repro-hover.png"),
    animations: "disabled",
  });

  await page.mouse.down();
  await page.mouse.move(hit.x + 120, hit.y + 70, { steps: 14 });
  await expect(canvas).toHaveClass(/dragging/);
  await page.screenshot({
    path: testInfo.outputPath("copied-repro-drag.png"),
    animations: "disabled",
  });

  await page.mouse.up();
  await expect(canvas).not.toHaveClass(/dragging/);
});
